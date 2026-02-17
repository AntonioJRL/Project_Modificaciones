from odoo import api, fields, models, _
from odoo.tools import format_amount
from odoo.tools.float_utils import float_round
from dateutil.relativedelta import relativedelta
import json
from collections import defaultdict
import logging
from odoo.tools import Markup

_logger = logging.getLogger(__name__)


class ProjectProfitabilityReport(models.TransientModel):
    _name = 'project.profitability.report'
    _description = 'Reporte de Rentabilidad de Proyecto'

    def _default_project_ids(self):
        return self.env.context.get('active_ids') if self.env.context.get('active_model') == 'project.project' else []

    project_ids = fields.Many2many('project.project', string='Proyectos',
                                   default=_default_project_ids,
                                   required=True, domain="[('is_proyecto_obra', '=', True)]", help="Proyectos a los cuales se les realizará la revisión de rentabilidad.")

    # Nombre
    name = fields.Char(string='Nombre', compute='_compute_nombre')

    @api.depends('project_ids')
    def _compute_nombre(self):
        """Calcula el nombre del reporte basado en los proyectos seleccionados."""
        for wizard in self:
            if not wizard.project_ids:
                wizard.name = 'Dashboard: Sin Proyecto'
            elif len(wizard.project_ids) == 1:
                wizard.name = f"Dashboard Proyecto: {wizard.project_ids.display_name}"
            else:
                # Limitar a 3 nombres para evitar títulos demasiado largos
                names = wizard.project_ids.mapped('name')
                if len(names) > 3:
                    display_text = f"{', '.join(names[:3])} (+{len(names)-3})"
                else:
                    display_text = ", ".join(names)
                wizard.name = f"Dashboard Proyectos: {display_text}"

    # Filtros Principales
    filter_type = fields.Selection([
        ('all', 'Todas las Tareas'),
        ('filter', 'Selección Manual')
    ], string='Tareas', default='all', required=True)

    task_ids = fields.Many2many('project.task', string='Tareas Específicas',
                                domain="[('project_id', 'in', project_ids)]")

    task_state_filter = fields.Selection([
        ('all', 'Todas'),
        ('01_in_progress', 'En Proceso'),
        ('1_done', 'Hecho'),
        ('1_canceled', 'Cancelado'),
        ('04_waiting_normal', 'Esperando'),
        ('03_approved', 'Aprobado'),
        ('02_changes_requested', 'Cambios Solicitados'),
    ], string="Estado de Tareas", default='all')

    include_archived = fields.Boolean(
        string="Incluir Tareas Archivadas", default=False)

    include_analytic_account = fields.Boolean(
        string="Incluir por Cuenta Analítica",
        default=True,
        help="Si está activo, busca también registros vinculados a la Cuenta Analítica del Proyecto, no solo al Proyecto directamente."
    )

    # Filtros de Fecha
    chart_type = fields.Selection([
        ('pie', 'Gráfico de Costos'),
        ('waterfall', 'Cascada de Rentabilidad'),
        ('line', 'Evolución Temporal'),
        ('top_tasks', 'Top 10 Tareas')
    ], string='Tipo de Gráfico', default='pie', required=True)

    date_filter_type = fields.Selection([
        ('none', 'Sin Filtro de Fecha'),
        ('today', 'Hoy'),
        ('this_month', 'Este Mes'),
        ('this_year', 'Este Año'),
        ('custom', 'Personalizado')
    ], string='Periodo', default='none', required=True)

    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')

    # Filtro de Ubicacion
    ubicacion_ids = fields.Many2many(
        'project.ubicacion', string='Ubicaciones',
        help="Filtrar proyectos por su ubicación (sitio de trabajo).")

    date = fields.Date(default=fields.Date.context_today)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    # Contenido HTML renderizado
    content = fields.Html(string='Contenido',
                          sanitize=False, compute='_compute_content')

    # Métricas Agregadas (Compute)
    timesheet_hours = fields.Float(string='Horas', compute='_compute_stats')
    timesheet_cost = fields.Monetary(
        string='Costo Horas', currency_field='currency_id', compute='_compute_profitability')

    total_expenses = fields.Monetary(
        string='Total Gastos', compute='_compute_profitability', currency_field='currency_id')
    total_purchases = fields.Monetary(
        string='Total Compras', compute='_compute_profitability', currency_field='currency_id')
    total_stock_moves = fields.Monetary(
        string='Total Mov. Almacén', compute='_compute_profitability', currency_field='currency_id')

    expected_income = fields.Monetary(
        string='Ingresos Esperados', compute='_compute_profitability', currency_field='currency_id')
    invoiced_income = fields.Monetary(
        string='Facturado', compute='_compute_profitability', currency_field='currency_id')
    to_invoice_income = fields.Monetary(
        string='Por Facturar', compute='_compute_profitability', currency_field='currency_id')

    margin_total = fields.Monetary(
        string='Margen', compute='_compute_profitability', currency_field='currency_id')
    profit_percentage = fields.Float(
        string='% Rentabilidad', compute='_compute_profitability')

    # KPIs Counts
    task_count = fields.Integer(string='Tareas', compute='_compute_stats')
    sale_order_count = fields.Integer(
        string='Órdenes de Venta', compute='_compute_stats')
    purchase_count = fields.Integer(
        string='Órdenes de Compra', compute='_compute_stats')
    expense_count = fields.Integer(
        string='Gastos', compute='_compute_stats')
    requisition_count = fields.Integer(
        string='Requisiciones', compute='_compute_stats')
    stock_move_count = fields.Integer(
        string='Mov. Almacén', compute='_compute_stats')
    compensation_count = fields.Integer(
        string='Compensaciones', compute='_compute_stats')

    # Nuevo: Costos Comprometidos y KPIs
    purchase_committed = fields.Monetary(
        string='Costo Comprometido (Compras)', compute='_compute_profitability', currency_field='currency_id')
    purchase_cost_incurred = fields.Monetary(
        string='Costo Incurrido (Compras)', compute='_compute_profitability', currency_field='currency_id',
        help="Compras facturadas o recibidas")

    # KPIs Comparativos

    @api.onchange('date_filter_type')
    def _onchange_date_filter_type(self):
        today = fields.Date.context_today(self)
        if self.date_filter_type == 'today':
            self.date_from = today
            self.date_to = today
        elif self.date_filter_type == 'this_month':
            self.date_from = today.replace(day=1)
            self.date_to = today + relativedelta(months=1, day=1, days=-1)
        elif self.date_filter_type == 'this_year':
            self.date_from = today.replace(day=1, month=1)
            self.date_to = today.replace(day=31, month=12)
        elif self.date_filter_type == 'none':
            self.date_from = False
            self.date_to = False

        # Actualizar fechas de comparacion si aplica

    @api.onchange('ubicacion_ids')
    def _onchange_ubicacion_ids(self):
        """Limpia los proyectos seleccionados si no pertenecen a las nuevas ubicaciones"""
        if self.ubicacion_ids:
            self.project_ids = self.project_ids.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

    @api.onchange('filter_type', 'task_ids', 'task_state_filter',
                  'date_filter_type', 'date_from', 'date_to',
                  'include_archived', 'chart_type', 'ubicacion_ids',
                  'include_analytic_account')
    def _onchange_filters(self):
        """
        Se ejecuta cuando cambia cualquier filtro en la interfaz.
        Recalcula manualmente las métricas y el contenido para actualizar la vista
        antes de que el usuario guarde.
        """
        self._compute_stats()
        self._compute_profitability()
        self._compute_content()

    @api.onchange('project_ids')
    def _onchange_project_ids(self):
        """Limpia las tareas seleccionadas si no pertenecen a los nuevos proyectos"""
        if self.project_ids:
            self.task_ids = self.task_ids.filtered(
                lambda t: t.project_id in self.project_ids)
        else:
            self.task_ids = False

    def _get_date_domain(self, date_field):
        """Genera el dominio de fechas para el campo especificado"""
        self.ensure_one()
        if self.date_filter_type == 'none':
            return []

        domain = []
        if self.date_from:
            domain.append((date_field, '>=', self.date_from))
        if self.date_to:
            domain.append((date_field, '<=', self.date_to))
        return domain

    def _convert_amount(self, amount, src_currency, target_currency, date=None):
        """Convierte un monto de una moneda origen a una destino en una fecha dada."""
        if not src_currency:
            src_currency = self.env.company.currency_id
        if src_currency == target_currency:
            return amount
        return src_currency._convert(
            amount, target_currency, self.env.company, date or fields.Date.context_today(self))

    @api.depends('project_ids', 'filter_type', 'task_ids', 'task_state_filter', 'include_archived')
    def _get_filtered_tasks(self):
        """
        Retorna el recordset de tareas basado en los filtros aplicados.
        Este método es la FUENTE DE VERDAD para qué tareas se consideran en el análisis.
        """
        self.ensure_one()
        if not self.project_ids:
            return self.env['project.task']

        domain = [('project_id', 'in', self.project_ids.ids)]

        # Filtro por Ubicación
        if self.ubicacion_ids:
            domain.append(
                ('project_id.ubicacion', 'in', self.ubicacion_ids.ids))

        # Manejo de tareas archivadas
        context = self.env.context.copy()
        if self.include_archived:
            context['active_test'] = False
            Task = self.env['project.task'].with_context(context)
        else:
            Task = self.env['project.task']

        if self.filter_type == 'filter':
            if self.task_ids:
                return self.task_ids

        # Filtro por estado predefinido (En Proceso, Hecho, etc.)
        if self.task_state_filter == 'all':
            domain.append(('state', '!=', '1_canceled'))
        elif self.task_state_filter:
            # Mapeo directo para estados específicos
            domain.append(('state', '=', self.task_state_filter))

        return Task.search(domain)

    def _get_sale_order_lines(self):
        """Retorna las Líneas de Venta específicas vinculadas al proyecto/tareas."""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        final_domain = [('state', 'in', ['sale', 'done'])]

        # Date Filter (Applied to Order Date)
        if self.date_filter_type != 'none':
            if self.date_from:
                final_domain.append(
                    ('order_id.date_order', '>=', self.date_from))
            if self.date_to:
                final_domain.append(
                    ('order_id.date_order', '<=', self.date_to))

        # Criterios Principales
        # 1. Vinculado a Tarea
        # 2. Vinculado a Proyecto (Cabecera o Línea)
        # 3. Vinculado a Cuenta Analítica (Híbrido)

        # Base: Vinculado a tareas filtradas
        criteria = [('task_id', 'in', all_tasks.ids)]

        # Contexto de Proyectos
        projects = self.project_ids
        if self.ubicacion_ids:
            projects = projects.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

        if projects:
            # Opción A: Vinculación Directa por Proyecto
            project_domain = [('order_id.project_id', 'in', projects.ids)]
            if 'project_id' in self.env['sale.order.line']._fields:
                project_domain.append(('project_id', 'in', projects.ids))

            # Opción B: Vinculación por Cuenta Analítica (Si está activo)
            analytic_domain = []
            if self.include_analytic_account:
                analytics = projects.mapped('analytic_account_id')
                if analytics:
                    # Verificar campos disponibles en SOL y SO
                    if 'analytic_account_id' in self.env['sale.order']._fields:
                        analytic_domain.append(
                            ('order_id.analytic_account_id', 'in', analytics.ids))

                    # Odoo 17 usa analytic_distribution (JSON), búsqueda difícil por ORM simple.
                    # Buscamos campos legacy o custom si existen.
                    if 'analytic_account_id' in self.env['sale.order.line']._fields:
                        analytic_domain.append(
                            ('analytic_account_id', 'in', analytics.ids))

            # Combinar lógica: (Tarea) O (Proyecto) O (Analítica)
            # Pero la estructura es search([ (Base_Filtros_Globales) AND ( (Tarea) OR (Proyecto) OR (Analítica) ) ])
            # Aquí 'criteria' es una lista de condiciones OR.

            # Agregamos dominios de proyecto a criteria
            criteria.extend(project_domain)

            # Agregamos dominios analíticos a criteria
            criteria.extend(analytic_domain)

        # Construir dominio OR global para los criterios de vinculación
        # filter_domain AND ( Criterio1 OR Criterio2 OR ... )
        link_domain = []
        if len(criteria) > 1:
            link_domain = ['|'] * (len(criteria) - 1)
        link_domain += criteria

        # Combinar con dominio base (Estados y Fechas ya están en final_domain)
        # final_domain = [Conditions]
        # Queremos: final_domain AND link_domain

        return self.env['sale.order.line'].search(final_domain + link_domain)

    def _get_sale_orders(self):
        """Retorna las órdenes de venta distintas derivadas de las líneas"""
        return self._get_sale_order_lines().mapped('order_id')

    def _get_purchase_order_lines(self):
        """Retorna las Líneas de Compra específicas"""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # El estado de línea usualmente coincide con la orden, pero es más seguro verificar la orden.
        # POL no siempre tiene 'state'. PO sí.
        # En realidad purchase.order.line tiene 'state' relacionado a order.state usualmente.
        # Pero verifiquemos order_id.state en el dominio para alinearnos al estándar.
        final_domain = [('order_id.state', 'in', ['purchase', 'done'])]

        if self.date_filter_type != 'none':
            if self.date_from:
                final_domain.append(
                    ('order_id.date_order', '>=', self.date_from))
            if self.date_to:
                final_domain.append(
                    ('order_id.date_order', '<=', self.date_to))

        # Criterios Principales
        # 1. Vinculado a Tarea
        # 2. Vinculado a Proyecto
        # 3. Vinculado a Cuenta Analítica (Híbrido)

        # Base: Vinculado a tareas filtradas
        criteria = [('task_id', 'in', all_tasks.ids)]

        # Contexto de Proyectos
        projects = self.project_ids
        if self.ubicacion_ids:
            projects = projects.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

        if projects:
            # Opción A: Vinculación Directa por Proyecto
            project_domain = [('order_id.project_id', 'in', projects.ids)]
            if 'project_id' in self.env['purchase.order.line']._fields:
                project_domain.append(('project_id', 'in', projects.ids))

            # Opción B: Vinculación por Cuenta Analítica (Si está activo)
            analytic_domain = []
            if self.include_analytic_account:
                analytics = projects.mapped('analytic_account_id')
                if analytics:
                    # Verificar campos disponibles en POL y PO
                    if 'analytic_account_id' in self.env['purchase.order.line']._fields:
                        analytic_domain.append(
                            ('analytic_account_id', 'in', analytics.ids))

                    # A veces la cuenta analítica está en la cabecera (custom)
                    if 'analytic_account_id' in self.env['purchase.order']._fields:
                        analytic_domain.append(
                            ('order_id.analytic_account_id', 'in', analytics.ids))

            # Combinar lógica: (Tarea) O (Proyecto) O (Analítica)
            criteria.extend(project_domain)
            criteria.extend(analytic_domain)

        # Construir dominio OR global
        link_domain = []
        if len(criteria) > 1:
            link_domain = ['|'] * (len(criteria) - 1)
        link_domain += criteria

        return self.env['purchase.order.line'].search(final_domain + link_domain)

    def _get_purchase_orders(self):
        return self._get_purchase_order_lines().mapped('order_id')

    def _get_stock_moves(self):
        """Retorna los Movimientos de Almacén específicos"""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        final_domain = [('state', '=', 'done')]

        if self.date_filter_type != 'none':
            if self.date_from:
                final_domain.append(('date', '>=', self.date_from))
            if self.date_to:
                final_domain.append(('date', '<=', self.date_to))

        criteria = [('task_id', 'in', all_tasks.ids)]
        # Filtrar proyectos por Ubicación
        projects = self.project_ids
        if self.ubicacion_ids:
            projects = projects.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

        if projects:
            criteria.append(
                ('picking_id.project_id', 'in', projects.ids))
            if 'project_id' in self.env['stock.move']._fields:
                criteria.append(('project_id', 'in', projects.ids))

        if len(criteria) > 1:
            final_domain += ['|'] * (len(criteria) - 1)
        final_domain += criteria

        return self.env['stock.move'].search(final_domain)

    def _get_timesheets(self):
        """Returns specific Analytic Lines (Timesheets)"""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # Base Domain
        domain = []

        # 1. Contexto de Proyecto
        projects = self.project_ids
        if self.ubicacion_ids:
            projects = projects.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

        if projects:
            domain.append(('project_id', 'in', projects.ids))

        # 2. Lógica de Tareas / Huérfanos
        # Si se seleccionan tareas específicas, filtramos estrictamente por ellas.
        # Si NO se seleccionan tareas (Filtro 'Todas'), queremos incluir "Huérfanos" (Timesheets sin Tarea)
        # porque son parte del costo del proyecto.
        if self.task_ids:
            # Tareas específicas seleccionadas -> Filtro estricto
            domain.append(('task_id', 'in', all_tasks.ids))
        else:
            # Sin tareas específicas -> Permitir TODOS los timesheets del proyecto
            # Confiamos en el filtro project_id agregado en el paso 1.
            # NO filtramos por task_id aquí para obtener task_id=False (huérfanos) Y task_id=Cualquiera (vinculados).
            # Instrucción de usuario: "Si el usuario NO ha filtrado tareas específicas... permite que task_id sea False o cualquiera."
            pass

        # 3. Date Filter
        if self.date_filter_type != 'none':
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<=', self.date_to))

        return self.env['account.analytic.line'].sudo().search(domain)

    def _get_compensations(self):
        """Retorna las Líneas de Compensación específicas"""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # Dominio Base: Estado Aplicado (Solicitud estricta de usuario)
        domain = [('compensation_id.state', '=', 'applied')]

        # Vínculo Tarea / Proyecto
        # Verificar si project_id existe en compensation.line
        has_project = 'project_id' in self.env['compensation.line']._fields

        if has_project:
            # Lógica Inclusiva similar a Timesheets
            projects = self.project_ids
            if self.ubicacion_ids:
                projects = projects.filtered(
                    lambda p: p.ubicacion in self.ubicacion_ids)

            # (Tarea en Filtradas) O (Proyecto en Proyectos Y Tarea es False)
            domain.append('|')
            domain.append(('task_id', 'in', all_tasks.ids))
            domain.append('&')
            domain.append(('project_id', 'in', projects.ids))
            domain.append(('task_id', '=', False))
        else:
            # Fallback a solo vínculo de Tarea
            domain.append(('task_id', 'in', all_tasks.ids))

        # Filtro de Fecha
        # compensation.line podría no tener 'date', verificar campo o usar create_date
        date_field = 'create_date'
        if 'date' in self.env['compensation.line']._fields:
            date_field = 'date'

        if self.date_filter_type != 'none':
            if self.date_from:
                domain.append((date_field, '>=', self.date_from))
            if self.date_to:
                domain.append((date_field, '<=', self.date_to))

        return self.env['compensation.line'].search(domain)

    def _get_profitability_data(self, projects, date_from, date_to):
        """
        Calcula la rentabilidad para un set de proyectos en un rango de fechas.
        Retorna un diccionario con las métricas.
        """
        if not projects:
            return defaultdict(float)

        # Los helpers usan self.project_ids. Asumimos que projects pasado aquí == self.project_ids
        # o aceptamos que los helpers usan el contexto del wizard.

        target_currency = self.currency_id
        company_currency = self.env.company.currency_id

        # Helper para conversión con fecha específica
        def convert(amount, src_curr, date):
            return self._convert_amount(amount, src_curr, target_currency, date)

        # Helper para dominio de fechas dinámico (Uso local para Facturas)
        def get_date_domain(field_name):
            d_dom = []
            if date_from:
                d_dom.append((field_name, '>=', date_from))
            if date_to:
                d_dom.append((field_name, '<=', date_to))
            return d_dom

        # --- INGRESOS ---
        sols = self._get_sale_order_lines()
        expected = sum(convert(sol.price_subtotal, sol.currency_id, None)
                       for sol in sols)

        inv_domain = [('move_id.state', '=', 'posted')] + \
            get_date_domain('move_id.invoice_date')
        posted_lines = sols.mapped('invoice_lines').filtered_domain(inv_domain)
        invoiced = sum(convert(l.price_subtotal, l.currency_id,
                       l.move_id.invoice_date) for l in posted_lines)

        # To Invoice logic (simplified for report)
        # We use the un-invoiced amount of the filtered SOLs
        to_invoice = 0.0
        for sol in sols:
            # qty_to_invoice is natively computed
            qty_to_inv = sol.qty_to_invoice
            if qty_to_inv > 0:
                amount = qty_to_inv * sol.price_unit
                to_invoice += convert(amount, sol.currency_id,
                                      sol.order_id.date_order)

        # --- 2. COSTOS ---

        # A. GASTOS
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        expense_domain = self._get_expense_domain(all_tasks)
        expenses = self.env['hr.expense'].sudo().search(expense_domain)

        total_expenses = 0.0
        for exp in expenses:
            # Prio 1: Neto en Moneda Original (Ideal)
            if 'untaxed_amount_currency' in self.env['hr.expense']._fields:
                amount = exp.untaxed_amount_currency
            # Prio 2: Neto en Moneda Compañía
            elif 'untaxed_amount' in self.env['hr.expense']._fields:
                amount = exp.untaxed_amount
            # Prio 3: Fallback a Total (Bruto)
            else:
                amount = getattr(exp, 'total_amount_currency',
                                 0.0) or exp.total_amount

            total_expenses += convert(amount, exp.currency_id, exp.date)

        # B. COMPRAS (Estricto: Incurrido vs Comprometido)
        purchase_lines = self._get_purchase_order_lines()

        p_incurred = 0.0
        p_committed = 0.0

        for pl in purchase_lines:
            qty_done = max(pl.qty_invoiced, pl.qty_received)
            qty_ordered = pl.product_qty
            price_subtotal = pl.price_subtotal
            date_doc = pl.date_order

            if qty_ordered:
                ratio = qty_done / qty_ordered
            else:
                ratio = 0.0

            # Incurrido basado en el ratio del monto total (subtotal)
            amount_incurred = price_subtotal * ratio

            # Comprometido es el remanente para alcanzar el subtotal
            amount_committed = price_subtotal - amount_incurred

            # Convertir resultados a moneda del reporte
            if amount_incurred:
                p_incurred += convert(amount_incurred,
                                      pl.currency_id, date_doc)

            if amount_committed:
                p_committed += convert(amount_committed,
                                       pl.currency_id, date_doc)

        total_purchases = p_incurred + p_committed

        # C. STOCK (Valoración Real desde Capas - Layers)
        stock_moves = self._get_stock_moves()
        stock_cost = 0.0

        for move in stock_moves:
            # 1. Regla Anti-Duplicidad: Saltar si está vinculado a Compra
            if move.purchase_line_id or move.picking_id.purchase_id:
                continue

            # 2. Valoración (Fuente de Verdad)
            layers = move.stock_valuation_layer_ids
            move_cost = 0.0

            if layers:
                total_val = sum(abs(l.value) for l in layers)
                move_cost = convert(total_val, company_currency, move.date)
            else:
                val_unit = move.price_unit or move.product_id.standard_price
                qty = move.quantity if move.state == 'done' else move.product_uom_qty
                move_cost = convert(
                    val_unit * qty, company_currency, move.date)

            # 3. Lógica Financiera de Signos
            is_outgoing = move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'
            is_return = move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal'
            # Traslados Internos (Int -> Int) son Neutros (Efecto 0 en rentabilidad)

            if is_outgoing:
                stock_cost += move_cost
            elif is_return:
                stock_cost -= move_cost
            # else: traslado interno, ignorar adición de costo

        # D. MANO DE OBRA (Timesheets + Compensations)

        # 1. Timesheets (Líneas Analíticas)
        timesheets = self._get_timesheets()
        timesheet_cost_only = 0.0
        for ts in timesheets:
            # amount es usualmente negativo (costo). Sumamos abs().
            timesheet_cost_only += convert(abs(ts.amount),
                                           ts.currency_id, ts.date)

        # 2. Compensations
        # Las traemos para KPIs o potencial visualización, pero NO sumamos su costo
        # porque ya están incluidas en las Líneas Analíticas (Timesheets) según auditoría SQL.
        compensations = self._get_compensations()
        compensation_cost = 0.0
        # Bucle eliminado para evitar doble contabilidad.

        timesheet_cost = timesheet_cost_only + compensation_cost

        # TOTALES
        total_costs_real = total_expenses + total_purchases + stock_cost + timesheet_cost
        margin_total = invoiced - total_costs_real

        profit_percentage = 0.0
        if invoiced:
            profit_percentage = (margin_total / invoiced) * 100.0
        elif expected:
            profit_percentage = (margin_total / expected) * 100.0

        return {
            'expected_income': expected,
            'invoiced_income': invoiced,
            'to_invoice_income': to_invoice,
            'total_expenses': total_expenses,
            'total_purchases': total_purchases,
            'purchase_incurred': p_incurred,
            'purchase_committed': p_committed,
            'total_stock_moves': stock_cost,
            'timesheet_cost': timesheet_cost,
            'margin_total': margin_total,
            'profit_percentage': profit_percentage,
            'total_costs': total_costs_real
        }

    @api.depends('project_ids', 'filter_type', 'task_ids', 'task_state_filter',
                 'date_filter_type', 'date_from', 'date_to', 'include_archived',
                 'ubicacion_ids')
    def _compute_profitability(self):
        for wizard in self:
            # Helpers handle location filtering now (Strict Source of Truth)
            data = wizard._get_profitability_data(
                wizard.project_ids, wizard.date_from, wizard.date_to)

            wizard.expected_income = data['expected_income']
            wizard.invoiced_income = data['invoiced_income']
            wizard.to_invoice_income = data['to_invoice_income']
            wizard.total_expenses = data['total_expenses']
            wizard.total_purchases = data['total_purchases']
            wizard.purchase_cost_incurred = data['purchase_incurred']
            wizard.purchase_committed = data['purchase_committed']
            wizard.total_stock_moves = data['total_stock_moves']
            wizard.timesheet_cost = data['timesheet_cost']
            wizard.margin_total = data['margin_total']
            wizard.profit_percentage = data['profit_percentage']

    def _check_date(self, date_value):
        """Helper para filtrar en memoria fechas"""
        if not date_value:
            return False
        if self.date_filter_type == 'none':
            return True
        d = date_value.date() if hasattr(date_value, 'date') else date_value
        if self.date_from and d < self.date_from:
            return False
        if self.date_to and d > self.date_to:
            return False
        return True

    @api.depends('project_ids', 'filter_type', 'task_ids', 'task_state_filter', 'date_filter_type', 'date_from', 'date_to', 'chart_type', 'ubicacion_ids', 'include_archived')
    def _compute_content(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            all_tasks = tasks | tasks.mapped('child_ids')
            all_task_ids = all_tasks.ids
            company_currency = wizard.env.company.currency_id
            target_currency = wizard.currency_id

            # Listado de Movimientos de Stock
            # Fuente de Verdad: Helper
            moves = wizard._get_stock_moves().sorted('date', reverse=True)

            stock_moves_list = []
            state_map = {
                'draft': 'Borrador', 'waiting': 'Esperando',
                'confirmed': 'En espera', 'assigned': 'Reservado',
                'done': 'Hecho', 'cancel': 'Cancelado',
            }

            base_url = wizard.env['ir.config_parameter'].sudo(
            ).get_param('web.base.url')

            for move in moves:
                # 1. Regla Anti-Duplicidad
                if move.purchase_line_id or move.picking_id.purchase_id:
                    continue

                # Lógica copiada de _get_profitability_data para consistencia estricta
                layers = move.stock_valuation_layer_ids
                total_cost = 0.0

                # Helper para conversión en bucle
                def convert_s(amount, src, date):
                    return wizard._convert_amount(amount, src, target_currency, date)

                if layers:
                    total_val = sum(abs(l.value) for l in layers)
                    total_cost = convert_s(
                        total_val, company_currency, move.date)
                else:
                    val_unit = move.price_unit or move.product_id.standard_price
                    qty = move.quantity if move.state == 'done' else move.product_uom_qty
                    total_cost = convert_s(
                        val_unit * qty, company_currency, move.date)

                # Definir Signo y Etiqueta
                is_outgoing = move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'
                is_return = move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal'

                # Etiqueta por defecto
                move_label = move.reference

                if is_outgoing:
                    pass  # Costo es positivo
                elif is_return:
                    total_cost = -total_cost
                else:
                    # Interno (Int -> Int) -> Resguardo
                    total_cost = 0.0
                    move_label = f"{move.reference} (Resguardo / Interno)"

                # Calcular precio unitario efectivo para visualización
                qty_display = move.quantity if move.state == 'done' else move.product_uom_qty
                unit_cost_display = abs(
                    total_cost / qty_display) if qty_display else 0.0

                move_url = f"{base_url}/web#id={move.id}&model=stock.move&view_type=form"

                stock_moves_list.append({
                    'product_name': move.product_id.display_name,
                    'task_name': move.task_id.name or '-',  # Manejar tarea faltante
                    # Manejar enlace directo a proyecto
                    'project_name': move.task_id.project_id.name or move.project_id.name,
                    'date': move.date,
                    'quantity': qty_display,
                    'uom': move.product_uom.name,
                    'reference': move.reference,
                    'picking': move.picking_id.name,
                    'picking_url': move_url,
                    'price_unit': unit_cost_display,
                    'total_cost': total_cost,
                    'state_label': state_map.get(move.state, move.state),
                    'state_raw': move.state,
                    'location_id': move.location_id.display_name,
                    'location_dest_id': move.location_dest_id.display_name,
                    'lot_name': ", ".join(move.move_line_ids.mapped('lot_id.name')) or "-"
                })

            # Compras Detalladas
            purchases_list = []
            # Use Source of Truth Helper
            purchase_lines = wizard._get_purchase_order_lines().sorted(
                'create_date', reverse=True)

            purchase_state_map = {
                'draft': 'Borrador', 'sent': 'Enviado', 'to approve': 'Por Aprobar',
                'purchase': 'Pedido Compra', 'done': 'Bloqueado', 'cancel': 'Cancelado'
            }

            for line in purchase_lines:
                purchases_list.append({
                    'order_name': line.order_id.name,
                    'order_id': line.order_id.id,
                    'project_name': line.task_id.project_id.name or line.project_id.name,
                    'task_name': line.task_id.name or '-',
                    'purchase_order_model': 'purchase.order',  # For linking
                    'date': line.date_order,
                    'partner': line.partner_id.name,
                    'product': line.product_id.display_name,
                    'qty': line.product_qty,
                    'price_unit': line.price_unit,
                    'total': wizard._convert_amount(line.price_subtotal, line.currency_id, target_currency, line.order_id.date_order),
                    'currency': target_currency.symbol,  # Converted currency
                    'state': purchase_state_map.get(line.order_id.state, line.order_id.state),
                    'state_raw': line.order_id.state,
                })

            # Gastos Detallados
            expenses_list = []
            exp_domain = wizard._get_expense_domain(all_tasks)

            expenses = self.env['hr.expense'].sudo().search(
                exp_domain, order='date desc')

            expense_state_map = {
                'draft': 'Borrador', 'reported': 'Enviado', 'approved': 'Aprobado',
                'post': 'Publicado', 'done': 'Pagado', 'refused': 'Rechazado'
            }

            for exp in expenses:
                # URL
                exp_url = f"/web#id={exp.id}&model=hr.expense&view_type=form"

                # Calculate Amount for Display
                if 'untaxed_amount_currency' in self.env['hr.expense']._fields:
                    amount_display = exp.untaxed_amount_currency
                elif 'untaxed_amount' in self.env['hr.expense']._fields:
                    amount_display = exp.untaxed_amount
                else:
                    amount_display = getattr(
                        exp, 'total_amount_currency', 0.0) or exp.total_amount

                expenses_list.append({
                    'name': exp.name,
                    'employee': exp.employee_id.name,
                    'project_name': exp.task_id.project_id.name or exp.project_id.name if 'project_id' in exp else '-',
                    'task_name': exp.task_id.name or '-',
                    'date': exp.date,
                    'product': exp.product_id.display_name,
                    'total': wizard._convert_amount(amount_display, exp.currency_id, target_currency, exp.date),
                    'currency': target_currency.symbol,  # Converted to report currency
                    'state': expense_state_map.get(exp.state, exp.state),
                    'state_raw': exp.state,
                    'sheet_name': exp.sheet_id.name,
                    'exp_url': exp_url
                })

            # Chart Data
            total_cost_base = wizard.total_expenses + wizard.total_purchases + \
                wizard.total_stock_moves + wizard.timesheet_cost or 1.0

            p_stock = (wizard.total_stock_moves / total_cost_base) * 100
            p_purchases = (wizard.total_purchases / total_cost_base) * 100
            p_timesheets = (wizard.timesheet_cost / total_cost_base) * 100
            p_expenses = (wizard.total_expenses / total_cost_base) * 100

            c_stock = f"#dc3545 0% {p_stock:.2f}%"
            c_purch = f"#0d6efd {p_stock:.2f}% {p_stock + p_purchases:.2f}%"
            c_time = f"#fd7e14 {p_stock + p_purchases:.2f}% {p_stock + p_purchases + p_timesheets:.2f}%"
            c_exp = f"#6610f2 {p_stock + p_purchases + p_timesheets:.2f}% 100%"

            chart_style = f"width: 100%; height: 100%; border-radius: 50%; background: conic-gradient({c_stock}, {c_purch}, {c_time}, {c_exp});"

            chart_data = {
                'stock_pct': p_stock,
                'purchases_pct': p_purchases,
                'timesheets_pct': p_timesheets,
                'expenses_pct': p_expenses,
                'style': chart_style
            }

            # --- CÁLCULO DE GRÁFICO DE COLUMNAS (CASCADA REAL) ---
            column_data = []
            if wizard.chart_type == 'waterfall':
                if not wizard.currency_id:
                    currency = company_currency
                else:
                    currency = wizard.currency_id

                rev = wizard.invoiced_income
                # Costos (Negativos para pasos de cascada)
                exp = -wizard.total_expenses
                # Compras Simplificadas
                pur_total = -wizard.total_purchases
                stk = -wizard.total_stock_moves
                tsh = -wizard.timesheet_cost

                final_margin = rev + exp + pur_total + stk + tsh

                # Estructura: (Etiqueta, Valor, Tipo, Color)
                # Pasos:
                # 1. Ingresos (Base) -> Inicia en 0, Altura = Rev
                # 2. Gastos -> Inicia en Rev, Altura = -Exp (Baja)
                # ...
                # Último: Margen -> Inicia en 0, Altura = Margen (o residuo)

                waterfall_steps = [
                    {'label': 'Ingresos', 'val': rev,
                        'color': '#198754', 'is_total': False},
                    {'label': 'Gastos', 'val': exp,
                        'color': '#6f42c1', 'is_total': False},
                    {'label': 'Compras', 'val': pur_total,
                     'color': '#0d6efd', 'is_total': False},
                    {'label': 'Stock', 'val': stk,
                        'color': '#dc3545', 'is_total': False},
                    {'label': 'Mano de Obra', 'val': tsh,
                        'color': '#fd7e14', 'is_total': False},
                    {'label': 'Margen Final', 'val': final_margin,
                        'color': '#20c997', 'is_total': True},
                ]

                # Calculate Accumulators for visualization positioning
                current_y = 0.0
                max_val = 0.0
                min_val = 0.0

                # Pre-pass to find range (to scale)
                # We need to track the "Peak" of the waterfall to scale Y axis.
                running = 0.0
                peaks = [0.0]
                for step in waterfall_steps:
                    if step['label'] == 'Ingresos':
                        running = step['val']
                    elif step['is_total']:
                        pass  # Total stands on 0 usually
                    else:
                        running += step['val']  # Val is negative
                    peaks.append(running)
                    # Individual bar height check
                    peaks.append(abs(step['val']))

                max_val = max(peaks + [rev]) * 1.1 or 1.0

                current_y = 0.0

                for step in waterfall_steps:
                    val = step['val']

                    if step['label'] == 'Ingresos':
                        # Base bar
                        y_start = 0
                        y_end = val
                        current_y = val
                    elif step['is_total']:
                        # Final bar from 0 to current_y (which should equal val)
                        y_start = 0
                        y_end = current_y  # Should be same as val theoretically
                    else:
                        # Step bar
                        y_start = current_y
                        y_end = current_y + val
                        current_y = y_end

                    # Determinar propiedades geométricas (porcentaje de altura)
                    # Asumimos 0 abajo (0%) y Max arriba (100%)
                    # Cascada funciona mejor con positivos, pero manejamos negativos visualmente.
                    # Mapeamos [0, max_val] a [0, 100%]

                    b_bottom = (min(y_start, y_end) / max_val) * 100.0
                    b_height = (abs(val) / max_val) * 100.0

                    column_data.append({
                        'label': step['label'],
                        'amount': val,
                        'bottom': b_bottom,
                        'height': b_height,
                        'color': step['color'],
                        'is_negative': val < 0
                    })

            # --- PREPARE DATA FOR TOP 5 AND LINE CHART ---
            # We need 'sols' and 'comp_lines' which are not yet in local scope of _compute_content
            # Reuse tasks logic
            all_tasks = self.env['project.task'].browse(all_task_ids)
            sols = all_tasks.mapped('sale_line_id')

            # Timesheets (Cost from Analytic Lines)
            ts_domain = wizard._get_project_task_domain()
            ts_domain += wizard._get_date_domain('date')

            timesheets = self.env['account.analytic.line'].search(
                ts_domain, order='date desc')

            timesheets_list = []

            for al in timesheets:
                # URL
                ts_url = f"/web#id={al.id}&model=account.analytic.line&view_type=form"

                # Cost is negative in amount. We want positive magnitude.
                cost = -al.amount

                timesheets_list.append({
                    'employee': al.employee_id.name,
                    'project_name': al.project_id.name,
                    'date': al.date,
                    'description': al.name,
                    'task': al.task_id.name or '-',
                    'total': cost,
                    'currency': al.currency_id.symbol,
                    'state_label': 'Validado',
                    'state_raw': 'validated',
                    'ts_url': ts_url
                })

            # --- GENERACIÓN DE DATOS PARA GRÁFICO DE LÍNEA ---
            line_chart_svg = ""
            if wizard.chart_type == 'line':
                # 1. Agregar Datos por Fecha
                date_data = defaultdict(lambda: {'income': 0.0, 'cost': 0.0})

                # Ingresos (Facturas)
                # Re-fetch líneas publicadas para asegurar acceso a fechas
                inv_domain_line = [('move_id.state', '=', 'posted'), ('sale_line_ids', 'in', sols.ids)] + \
                    wizard._get_date_domain('move_id.invoice_date')
                invoiced_lines = self.env['account.move.line'].search(
                    inv_domain_line)

                for line in invoiced_lines:
                    d = line.move_id.invoice_date
                    if d:
                        # Fix: Convertir a moneda reporte
                        date_data[d]['income'] += wizard._convert_amount(
                            line.price_subtotal, line.currency_id, target_currency, d)

                # Costs
                # Expenses
                for exp in expenses:
                    if exp.date:
                        date_data[exp.date]['cost'] += wizard._convert_amount(
                            exp.total_amount, exp.currency_id, target_currency, exp.date)

                # Purchases (Separated Incurred vs Committed?)
                # For graph, we usually show Incurred cost in the line.
                for line in purchase_lines:
                    d = line.date_order.date() if line.date_order else False
                    if d:
                        # Estimate portion incurred?
                        # Simplification: In line chart, put the whole amount on date_order
                        # OR only the incurred part.
                        # Let's plot Incurred Cost on date_order.
                        # Logic simplified: Use Total Ordered Value on Order Date
                        cost = line.product_qty * line.price_unit
                        date_data[d]['cost'] += wizard._convert_amount(
                            cost, line.currency_id, target_currency, line.date_order)

                # Stock
                for move in moves:  # Fixed variable name from stock_moves to moves
                    d = move.date.date() if move.date else False
                    if d:
                        idx_cost = move.price_unit or move.product_id.standard_price
                        qty = move.quantity if move.state == 'done' else move.product_uom_qty
                        cost_native = idx_cost * qty
                        date_data[d]['cost'] += wizard._convert_amount(
                            cost_native, company_currency, target_currency, move.date)

                # Timesheets
                # Timesheets (AAL)
                for al in timesheets:
                    d = al.date
                    if d and wizard._check_date(d):
                        # Cost is positive magnitude of amount (which is negative)
                        cost = -al.amount
                        date_data[d]['cost'] += wizard._convert_amount(
                            cost, al.currency_id, target_currency, al.date)

                # 2. Sort Dates and Fill Gaps (Optional, but better for lines)
                if date_data:
                    sorted_dates = sorted(date_data.keys())
                    min_date = sorted_dates[0]
                    max_date = sorted_dates[-1]

                    # Create list of points (CUMULATIVE S-CURVE)
                    points = []
                    current = min_date

                    cum_income = 0.0
                    cum_cost = 0.0

                    for i in range(len(sorted_dates)):
                        current_date = sorted_dates[i]
                        val = date_data.get(
                            current_date, {'income': 0.0, 'cost': 0.0})

                        cum_income += val['income']
                        cum_cost += val['cost']

                        margin = cum_income - cum_cost
                        margin_pct = (margin / cum_income *
                                      100.0) if cum_income else 0.0

                        points.append({
                            'date': current_date,
                            'date_str': current_date.strftime('%d/%m'),
                            'income': cum_income,
                            'cost': cum_cost,
                            'margin_pct': margin_pct
                        })

                    # 3. Generate SVG with Gradients and Tooltips
                    w, h = 800, 380
                    padding = 50

                    # Scales
                    max_val_chart = max([max(p['income'], p['cost'])
                                        for p in points]) or 1.0
                    max_val_chart = max_val_chart * 1.1  # Headroom

                    # Margin limits (handle negative)
                    margins = [p['margin_pct'] for p in points]
                    min_margin = min(margins) if margins else 0
                    max_margin = max(margins) if margins else 100
                    if min_margin > 0:
                        min_margin = 0
                    if max_margin < 100:
                        max_margin = 100
                    margin_range = max_margin - min_margin or 1.0

                    # Helpers
                    def get_y(val):
                        # Invert Y (SVG 0 is top)
                        return h - padding - ((val / max_val_chart) * (h - 2 * padding))

                    def get_y_pct(pct):
                        # Secondary Axis for %
                        # Normalize pct to 0-1 range within the chart area
                        return h - padding - (((pct - min_margin) / margin_range) * (h - 2 * padding))

                    def get_x(idx):
                        return padding + (idx * (w - 2 * padding) / (len(points) - 1 if len(points) > 1 else 1))

                    # Paths and Points
                    path_income_cmds = []
                    path_cost_cmds = []
                    path_margin_cmds = []

                    income_points_svg = ""
                    cost_points_svg = ""
                    margin_points_svg = ""

                    for i, p in enumerate(points):
                        cx = get_x(i)
                        cy_inc = get_y(p['income'])
                        cy_cst = get_y(p['cost'])
                        cy_mar = get_y_pct(p['margin_pct'])

                        cmd = "M" if i == 0 else "L"
                        path_income_cmds.append(f"{cmd} {cx:.1f},{cy_inc:.1f}")
                        path_cost_cmds.append(f"{cmd} {cx:.1f},{cy_cst:.1f}")
                        path_margin_cmds.append(f"{cmd} {cx:.1f},{cy_mar:.1f}")

                        # Markers with Tooltips using <title>
                        income_points_svg += f"""
                        <circle cx="{cx:.1f}" cy="{cy_inc:.1f}" r="4" fill="#28a745" stroke="white" stroke-width="2">
                            <title>Ingresos {p['date_str']}: {format_amount(self.env, p['income'], wizard.currency_id)}</title>
                        </circle>
                        """
                        cost_points_svg += f"""
                        <circle cx="{cx:.1f}" cy="{cy_cst:.1f}" r="4" fill="#dc3545" stroke="white" stroke-width="2">
                            <title>Costos {p['date_str']}: {format_amount(self.env, p['cost'], wizard.currency_id)}</title>
                        </circle>
                        """
                        margin_points_svg += f"""
                        <circle cx="{cx:.1f}" cy="{cy_mar:.1f}" r="4" fill="#ffc107" stroke="white" stroke-width="2">
                            <title>Margen {p['date_str']}: {p['margin_pct']:.2f}%</title>
                        </circle>
                        """

                    path_income_str = " ".join(path_income_cmds)
                    path_cost_str = " ".join(path_cost_cmds)
                    path_margin_str = " ".join(path_margin_cmds)

                    # Areas (Close path to bottom)
                    y_bottom = h - padding
                    path_income_area = f"{path_income_str} L {get_x(len(points)-1):.1f},{y_bottom} L {get_x(0):.1f},{y_bottom} Z"
                    path_cost_area = f"{path_cost_str} L {get_x(len(points)-1):.1f},{y_bottom} L {get_x(0):.1f},{y_bottom} Z"

                    # Ticks and Grid
                    # Y Axis (Left - Currency)
                    y_ticks = []
                    for i in range(5):
                        pct = i / 4.0
                        val = max_val_chart * pct
                        y_pos = get_y(val)
                        y_ticks.append(
                            f'<line x1="{padding}" y1="{y_pos}" x2="{w-padding}" y2="{y_pos}" stroke="#e9ecef" stroke-width="1" stroke-dasharray="4"/>')
                        y_ticks.append(
                            f'<text x="{padding-10}" y="{y_pos+4}" text-anchor="end" font-size="10" fill="#6c757d" font-family="sans-serif">{int(val)}</text>')

                    # Y Axis (Right - Percentage)
                    for i in range(5):
                        pct_rel = i / 4.0
                        val_pct = min_margin + (margin_range * pct_rel)
                        y_pos = get_y_pct(val_pct)
                        # No grid lines for secondary axis to avoid clutter
                        y_ticks.append(
                            f'<text x="{w-padding+10}" y="{y_pos+4}" text-anchor="start" font-size="10" fill="#ffc107" font-family="sans-serif">{int(val_pct)}%</text>')

                    # X Axis (First, Middle, Last)
                    x_ticks = []
                    step = 1
                    if len(points) > 12:
                        step = len(points) // 6

                    for i in range(0, len(points), step):
                        x_pos = get_x(i)
                        lbl = points[i]['date_str']
                        x_ticks.append(
                            f'<text x="{x_pos}" y="{h-padding+20}" text-anchor="middle" font-size="10" fill="#6c757d" font-family="sans-serif">{lbl}</text>')

                    line_chart_svg = Markup(f"""
                    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:auto; max-height:400px; font-family:-apple-system,system-ui,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
                         <defs>
                            <linearGradient id="gradIncome" x1="0%" y1="0%" x2="0%" y2="100%">
                                <stop offset="0%" style="stop-color:#28a745;stop-opacity:0.3" />
                                <stop offset="100%" style="stop-color:#28a745;stop-opacity:0" />
                            </linearGradient>
                            <linearGradient id="gradCost" x1="0%" y1="0%" x2="0%" y2="100%">
                                <stop offset="0%" style="stop-color:#dc3545;stop-opacity:0.3" />
                                <stop offset="100%" style="stop-color:#dc3545;stop-opacity:0" />
                            </linearGradient>
                            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                                <feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#000000" flood-opacity="0.1"/>
                            </filter>
                        </defs>
                        
                        <!-- Grid -->
                        {"".join(y_ticks)}
                        
                        <!-- Axis Lines -->
                        <line x1="{padding}" y1="{h-padding}" x2="{w-padding}" y2="{h-padding}" stroke="#dee2e6" stroke-width="1"/>
                        <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{h-padding}" stroke="#dee2e6" stroke-width="1"/>

                        <!-- Areas -->
                        <path d="{path_income_area}" fill="url(#gradIncome)" />
                        <path d="{path_cost_area}" fill="url(#gradCost)" />
                        
                        <!-- Lines -->
                        <path d="{path_income_str}" fill="none" stroke="#28a745" stroke-width="2.5" filter="url(#shadow)" />
                        <path d="{path_cost_str}" fill="none" stroke="#dc3545" stroke-width="2.5" filter="url(#shadow)" />
                        <path d="{path_margin_str}" fill="none" stroke="#ffc107" stroke-width="2.5" stroke-dasharray="5,5" filter="url(#shadow)" />
                        
                        <!-- Markers (Points) -->
                        <g class="markers-group">
                            {income_points_svg}
                            {cost_points_svg}
                            {margin_points_svg}
                        </g>

                        <!-- Axis Labels -->
                        {"".join(x_ticks)}
                        
                        <!-- Legend overlay -->
                        <g transform="translate({w-280}, 20)">
                            <rect width="250" height="30" rx="5" fill="white" fill-opacity="0.8" stroke="#dee2e6" />
                            <circle cx="20" cy="15" r="4" fill="#28a745" />
                            <text x="30" y="19" font-size="11" fill="#333" font-weight="bold">Ingresos</text>
                            <circle cx="90" cy="15" r="4" fill="#dc3545" />
                            <text x="100" y="19" font-size="11" fill="#333" font-weight="bold">Costos</text>
                            <circle cx="150" cy="15" r="4" fill="#ffc107" />
                            <text x="160" y="19" font-size="11" fill="#333" font-weight="bold">Margen %</text>
                        </g>
                    </svg>
                    """)
                else:
                    line_chart_svg = Markup(
                        '<div class="text-center p-5 text-muted">Sin datos para el rango seleccionado</div>')

            # --- ALERTS CALCULATION ---
            alert_negative_profit = False
            alert_low_margin = False

            # Using wizard computes directly which are already calculated in _compute_profitability
            # Margin & Percentage are in wizard.margin_total and wizard.profit_percentage

            # 1. Beneficio Negativo (Costo > Ingreso)
            if wizard.margin_total < 0:
                alert_negative_profit = True

            # 2. Margen Bajo (Positivo pero < 10%)
            # Asumimos profit_percentage base 0-100
            elif wizard.profit_percentage < 10.0 and wizard.invoiced_income > 0:
                alert_low_margin = True

            values = {
                'wizard': wizard,
                'stock_moves_list': stock_moves_list,
                'purchases_list': purchases_list,
                'expenses_list': expenses_list,
                'timesheets_list': timesheets_list,
                'chart_data': chart_data,
                'column_data': column_data,
                'line_chart_svg': line_chart_svg,

                'alert_negative_profit': alert_negative_profit,
                'alert_low_margin': alert_low_margin,
                'kpis': {

                    'purchase_committed': wizard.purchase_committed,
                    'purchase_incurred': wizard.purchase_cost_incurred
                },
                'profitability': {
                    'expected_income': wizard.expected_income,
                    'invoiced_income': wizard.invoiced_income,
                    'to_invoice_income': wizard.to_invoice_income,
                    'total_expenses': wizard.total_expenses,
                    'total_purchases': wizard.total_purchases,
                    'total_stock_moves': wizard.total_stock_moves,
                    'timesheet_cost': wizard.timesheet_cost,
                    'margin_total': wizard.margin_total,
                    'profit_percentage': wizard.profit_percentage,
                    'total_costs': wizard.total_expenses + wizard.total_purchases + wizard.total_stock_moves + wizard.timesheet_cost,
                },
                'format_monetary': lambda v: format_amount(self.env, float_round(v, precision_digits=2), wizard.currency_id),
                'format_percentage': lambda v: f"{v:.2f}%"
            }

            wizard.content = self.env['ir.qweb']._render(
                'project_modificaciones.project_profitability_template', values)

    def _get_project_task_domain(self, model_prefix=''):
        """
        Retorna un dominio que incluye:
        1. Registros vinculados a las tareas filtradas.
        2. Registros vinculados al proyecto pero SIN tarea (costos globales del proyecto).
        """
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        task_field = f'{model_prefix}task_id'
        project_field = f'{model_prefix}project_id'

        domain = [(task_field, 'in', all_tasks.ids)]

        if not self.task_ids and self.project_ids:
            return [
                '|',
                (task_field, 'in', all_tasks.ids),
                '&',
                (project_field, 'in', self.project_ids.ids),
                (task_field, '=', False)
            ]

        return domain

    def _get_expense_domain(self, all_tasks):
        """Helper para asegurar dominio consistente para gastos"""
        self.ensure_one()
        domain = []

        # Lógica de Vinculación (Proyecto / Tarea / Analítica)
        # Queremos: (Tarea) OR (Proyecto) OR (Analítica)

        criteria = [('task_id', 'in', all_tasks.ids)]
        projects = self.project_ids
        # Filtrar por ubicación si aplica (aunque self.project_ids ya debería estar filtrado o ser el contexto)
        if self.ubicacion_ids:
            projects = projects.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

        if 'project_id' in self.env['hr.expense']._fields:
            criteria.append(('project_id', 'in', projects.ids))

        # Lógica Analítica
        if self.include_analytic_account:
            analytics = projects.mapped('analytic_account_id')
            if analytics and 'analytic_account_id' in self.env['hr.expense']._fields:
                criteria.append(('analytic_account_id', 'in', analytics.ids))

        # Construir OR
        link_domain = []
        if len(criteria) > 1:
            link_domain = ['|'] * (len(criteria) - 1)
        link_domain += criteria

        # Combinar
        domain += link_domain

        # Filtros Adicionales (Estado y Fecha)
        domain += [('sheet_id.state', 'in', ['approve', 'post', 'done'])]
        domain += self._get_date_domain('date')
        return domain

    def _compute_stats(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            all_tasks = tasks | tasks.mapped('child_ids')

            # 0. Task Count
            wizard.task_count = len(tasks)

            # 1. Sale Orders (Source of Truth: Helper)
            wizard.sale_order_count = len(wizard._get_sale_orders())

            # 2. Purchase Orders (Source of Truth: Helper)
            wizard.purchase_count = len(wizard._get_purchase_orders())

            # 3. Expenses
            exp_domain = wizard._get_expense_domain(all_tasks)
            wizard.expense_count = self.env['hr.expense'].search_count(
                exp_domain)

            # 4. Requisiciones
            req_date_field = 'date_start' if 'date_start' in self.env[
                'employee.purchase.requisition']._fields else 'create_date'

            req_line_domain = wizard._get_project_task_domain()
            req_line_domain += [('requisition_product_id.state',
                                 'not in', ['cancelled', 'new'])]

            if wizard.date_filter_type != 'none':
                if wizard.date_from:
                    req_line_domain.append(
                        ('requisition_product_id.' + req_date_field, '>=', wizard.date_from))
                if wizard.date_to:
                    req_line_domain.append(
                        ('requisition_product_id.' + req_date_field, '<=', wizard.date_to))

            req_lines = self.env['requisition.order'].search(req_line_domain)
            wizard.requisition_count = len(
                req_lines.mapped('requisition_product_id'))

            # 5. Stock Moves (Fuente: Helper)
            wizard.stock_move_count = len(wizard._get_stock_moves())

            # 6. Timesheets (Fuente: Helper)
            timesheets = wizard._get_timesheets()
            wizard.timesheet_hours = sum(timesheets.mapped('unit_amount'))

            # 7. Compensations (Nómina) - Conteo de Solicitudes desde Líneas
            comp_lines = wizard._get_compensations()
            # Petición de usuario: Contar compensation.request (cabecera), no líneas
            wizard.compensation_count = len(
                comp_lines.mapped('compensation_id'))

    def action_recalculate(self):
        self._compute_stats()
        self._compute_profitability()
        self._compute_content()
        return True

    def _get_action_view_base(self, name, res_model, domain):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_mode': 'tree,form',
            'domain': domain,
            'target': 'current',
        }

    def action_view_tasks(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        return self._get_action_view_base('Tareas Filtradas', 'project.task', [('id', 'in', tasks.ids)])

    def action_view_sale_orders(self):
        self.ensure_one()
        return self._get_action_view_base('Órdenes de Venta', 'sale.order', [('id', 'in', self._get_sale_orders().ids)])

    def action_view_purchase_orders(self):
        self.ensure_one()
        return self._get_action_view_base('Órdenes de Compra', 'purchase.order', [('id', 'in', self._get_purchase_orders().ids)])

    def action_view_timesheets(self):
        self.ensure_one()

        # Revert to account.analytic.line (Hours Source)
        domain = self._get_project_task_domain()
        domain += self._get_date_domain('date')

        return self._get_action_view_base('Hojas de Horas', 'account.analytic.line', domain)

    def action_view_compensations(self):
        self.ensure_one()

        # Compensaciones (Fuente Nómina)
        # Filtro estricto de usuario: Solo 'applied'
        comp_domain = [('compensation_id.state', '=', 'applied')]

        if 'project_id' in self.env['compensation.line']._fields:
            comp_domain += self._get_project_task_domain()
        else:
            tasks = self._get_filtered_tasks()
            all_tasks = tasks | tasks.mapped('child_ids')
            comp_domain += [('task_id', 'in', all_tasks.ids)]

        # Añadir Filtro de Fecha
        date_field = 'create_date'
        if 'date' in self.env['compensation.line']._fields:
            date_field = 'date'

        comp_domain += self._get_date_domain(date_field)

        # Petición usuario: Ver compensation.request (header), no líneas
        lines = self.env['compensation.line'].search(comp_domain)
        requests = lines.mapped('compensation_id')

        return self._get_action_view_base('Compensaciones', 'compensation.request', [('id', 'in', requests.ids)])

    def action_view_expenses(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        domain = self._get_expense_domain(all_tasks)
        return self._get_action_view_base('Gastos', 'hr.expense', domain)

    def action_view_requisitions(self):
        self.ensure_one()

        line_domain = self._get_project_task_domain()
        line_domain += [('requisition_product_id.state',
                         'not in', ['cancelled', 'new'])]

        req_date_field = 'date_start' if 'date_start' in self.env[
            'employee.purchase.requisition']._fields else 'create_date'

        if self.date_filter_type != 'none':
            if self.date_from:
                line_domain.append(
                    ('requisition_product_id.' + req_date_field, '>=', self.date_from))
            if self.date_to:
                line_domain.append(
                    ('requisition_product_id.' + req_date_field, '<=', self.date_to))

        lines = self.env['requisition.order'].search(line_domain)
        requisition_ids = lines.mapped('requisition_product_id').ids

        return self._get_action_view_base('Requisiciones', 'employee.purchase.requisition', [('id', 'in', requisition_ids)])

    def action_view_stock_moves(self):
        self.ensure_one()
        picking_ids = self._get_stock_moves().mapped('picking_id').ids
        return self._get_action_view_base('Movimientos de Almacén', 'stock.picking', [('id', 'in', picking_ids)])
