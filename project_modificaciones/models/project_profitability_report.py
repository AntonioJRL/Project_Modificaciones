from odoo import api, fields, models, _
from odoo.tools import format_amount
from odoo.tools.float_utils import float_round
from odoo.osv import expression
from datetime import date
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

    project_ids = fields.Many2many(
        'project.project',
        string='Proyectos',
        default=_default_project_ids,
        required=True,
        domain="[('is_proyecto_obra', '=', True)]",
        help="Proyectos a los cuales se les realizará la revisión de rentabilidad.",
    )

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
                names = wizard.project_ids.mapped('name')
                if len(names) > 3:
                    display_text = f"{', '.join(names[:3])} (+{len(names) - 3})"
                else:
                    display_text = ", ".join(names)
                wizard.name = f"Dashboard Proyectos: {display_text}"

    # ── Filtros Principales ──────────────────────────────────────────────────

    filter_type = fields.Selection([
        ('all', 'Todas las Tareas'),
        ('filter', 'Selección Manual'),
    ], string='Tareas', default='all', required=True)

    task_ids = fields.Many2many(
        'project.task',
        string='Tareas Específicas',
        domain="[('project_id', 'in', project_ids)]",
    )

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
        default=False,
        help="Si está activo, busca también registros vinculados a la Cuenta Analítica del Proyecto.",
    )

    # ── Filtros de Fecha y Gráfico ───────────────────────────────────────────

    chart_type = fields.Selection([
        ('pie', 'Gráfico de Costos'),
        ('waterfall', 'Cascada de Rentabilidad'),
        ('line', 'Evolución Temporal'),
        ('top_tasks', 'Top 10 Tareas'),
    ], string='Tipo de Gráfico', default='pie', required=True)

    date_filter_type = fields.Selection([
        ('none', 'Sin Filtro de Fecha'),
        ('today', 'Hoy'),
        ('this_month', 'Este Mes'),
        ('this_year', 'Este Año'),
        ('custom', 'Personalizado'),
    ], string='Periodo', default='none', required=True)

    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')

    # ── Filtro de Ubicación ──────────────────────────────────────────────────

    ubicacion_ids = fields.Many2many(
        'project.ubicacion',
        string='Ubicaciones',
        help="Filtrar proyectos por su ubicación (sitio de trabajo).",
    )

    date = fields.Date(default=fields.Date.context_today)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    # ── Contenido HTML ───────────────────────────────────────────────────────

    content = fields.Html(string='Contenido',
                          sanitize=False, compute='_compute_content')

    # ── Métricas Agregadas (Compute) ─────────────────────────────────────────

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

    # ── KPIs de Conteo ───────────────────────────────────────────────────────

    task_count = fields.Integer(string='Tareas', compute='_compute_stats')
    sale_order_count = fields.Integer(
        string='Órdenes de Venta', compute='_compute_stats')
    purchase_count = fields.Integer(
        string='Órdenes de Compra', compute='_compute_stats')
    expense_count = fields.Integer(string='Gastos', compute='_compute_stats')
    requisition_count = fields.Integer(
        string='Requisiciones', compute='_compute_stats')
    stock_move_count = fields.Integer(
        string='Mov. Almacén', compute='_compute_stats')
    compensation_count = fields.Integer(
        string='Compensaciones', compute='_compute_stats')
    invoice_count = fields.Integer(
        string='Facturas de Cliente', compute='_compute_stats',
        help="Número de facturas de cliente (out_invoice) generadas a partir de las "
             "líneas de venta relacionadas al proyecto."
    )

    # ── Desglose contable por tipo de costo (lógica Odoo nativa) ─────────────

    expenses_billed = fields.Monetary(
        string='Gastos Contabilizados', compute='_compute_profitability',
        currency_field='currency_id',
        help="Gastos cuya hoja tiene un asiento contable confirmado (posted).")
    expenses_to_bill = fields.Monetary(
        string='Gastos Por Contabilizar', compute='_compute_profitability',
        currency_field='currency_id',
        help="Gastos aprobados sin asiento contable confirmado todavía.")

    purchases_billed = fields.Monetary(
        string='Compras Facturadas (Proveedor)', compute='_compute_profitability',
        currency_field='currency_id',
        help="Valor de las cantidades con vendor bill en estado posted (qty_invoiced).")
    purchases_to_bill = fields.Monetary(
        string='Compras Recibidas Sin Factura', compute='_compute_profitability',
        currency_field='currency_id',
        help="Valor recibido pero sin vendor bill confirmado aún (qty_received − qty_invoiced).")

    timesheet_billed = fields.Monetary(
        string='Horas Contabilizadas', compute='_compute_profitability',
        currency_field='currency_id',
        help="Costo de horas con asiento contable posted (ej. nómina validada).")
    timesheet_to_bill = fields.Monetary(
        string='Horas Sin Asiento', compute='_compute_profitability',
        currency_field='currency_id',
        help="Costo de horas registradas sin asiento contable confirmado.")

    stock_billed = fields.Monetary(
        string='Materiales Contabilizados', compute='_compute_profitability',
        currency_field='currency_id',
        help="Costo de movimientos de almacén con asiento de valoración posted.")
    stock_to_bill = fields.Monetary(
        string='Materiales Sin Asiento', compute='_compute_profitability',
        currency_field='currency_id',
        help="Costo de movimientos done sin asiento de valoración confirmado.")

    purchase_committed = fields.Monetary(
        string='Costo Comprometido (Compras)', compute='_compute_profitability',
        currency_field='currency_id')
    purchase_cost_incurred = fields.Monetary(
        string='Costo Incurrido (Compras)', compute='_compute_profitability',
        currency_field='currency_id',
        help="Compras facturadas o recibidas.")

    # =========================================================================
    # SECCIÓN: ONCHANGE
    # =========================================================================

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

    @api.onchange('ubicacion_ids')
    def _onchange_ubicacion_ids(self):
        """Limpia los proyectos seleccionados si no pertenecen a las nuevas ubicaciones."""
        if self.ubicacion_ids:
            self.project_ids = self.project_ids.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)

    @api.onchange(
        'filter_type', 'task_ids', 'task_state_filter',
        'date_filter_type', 'date_from', 'date_to',
        'include_archived', 'chart_type', 'ubicacion_ids',
        'include_analytic_account',
    )
    def _onchange_filters(self):
        self._compute_stats()
        self._compute_profitability()
        self._compute_content()

    @api.onchange('project_ids')
    def _onchange_project_ids(self):
        """Limpia las tareas seleccionadas si no pertenecen a los nuevos proyectos."""
        if self.project_ids:
            self.task_ids = self.task_ids.filtered(
                lambda t: t.project_id in self.project_ids)
        else:
            self.task_ids = False

    # =========================================================================
    # SECCIÓN: HELPERS GENÉRICOS
    # =========================================================================

    def _get_date_domain(self, date_field):
        """Genera el dominio de fechas para el campo especificado."""
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

    def _check_date(self, date_value):
        """Verifica si una fecha cae dentro del rango de filtro activo."""
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

    # =========================================================================
    # SECCIÓN: HELPERS INTERNOS CENTRALIZADOS
    # =========================================================================

    def _get_filtered_projects(self):
        """
        Retorna los proyectos del wizard ya filtrados por ubicación.
        """
        projects = self.project_ids
        if self.ubicacion_ids:
            projects = projects.filtered(
                lambda p: p.ubicacion in self.ubicacion_ids)
        return projects

    def _has_task_state_filter(self):
        """
        FIX 2 / FIX 3 — Helper centralizado para detectar si hay un filtro de estado
        de tarea activo (distinto de 'all').
        Cuando está activo, los dominios de proyecto se eliminan para que TODOS
        los registros pasen primero por el conjunto de tareas filtradas y no existan
        registros huérfanos de proyecto que eludan el filtro de estado.
        """
        return bool(self.task_state_filter and self.task_state_filter != 'all')

    def _build_analytic_domain(self, model_name, projects):
        """
        Construye el bloque de dominio para búsqueda por cuenta analítica (Odoo 17).
        Soporta campo legacy (analytic_account_id) y distribución JSON con índice GIN
        (analytic_distribution con operador 'in').
        """
        if not self.include_analytic_account or not projects:
            return []

        analytics = projects.mapped('analytic_account_id')
        if not analytics:
            return []

        model_fields = self.env[model_name]._fields
        analytic_criteria = []

        if 'analytic_account_id' in model_fields:
            analytic_criteria.append(
                [('analytic_account_id', 'in', analytics.ids)])

        if 'analytic_distribution' in model_fields:
            analytic_criteria.append(
                [('analytic_distribution', 'in', analytics.ids)])

        return expression.OR(analytic_criteria) if analytic_criteria else []

    def _get_purchase_linked_move_ids(self, move_ids):
        """
        Retorna el conjunto de IDs de stock.move vinculados a una línea de compra.
        """
        if not move_ids:
            return set()
        self.env.cr.execute(
            "SELECT id FROM stock_move WHERE id = ANY(%s) AND purchase_line_id IS NOT NULL",
            [move_ids],
        )
        return {row[0] for row in self.env.cr.fetchall()}

    def _filter_non_purchase_moves(self, moves):
        """
        Filtra un recordset de stock.move eliminando los vinculados a compras.
        Evita doble conteo entre el módulo de compras y el de almacén.
        """
        purchase_linked_ids = self._get_purchase_linked_move_ids(moves.ids)
        has_purchase_on_picking = 'purchase_id' in self.env['stock.picking']._fields
        return moves.filtered(
            lambda m: m.id not in purchase_linked_ids
            and not (has_purchase_on_picking and m.picking_id.purchase_id)
        )

    def _get_expense_amount_field(self):
        """
        Detecta qué campo de monto usar en hr.expense según la versión de Odoo.
        Centralizado para no repetir la detección dentro de bucles.
        """
        Expense = self.env['hr.expense']
        if 'untaxed_amount_currency' in Expense._fields:
            return 'untaxed_amount_currency'
        if 'untaxed_amount' in Expense._fields:
            return 'untaxed_amount'
        return None

    # =========================================================================
    # SECCIÓN: FUENTE DE VERDAD — TAREAS FILTRADAS
    # =========================================================================

    def _get_filtered_tasks(self):
        """
        Retorna el recordset de tareas basado en los filtros aplicados.
        FUENTE DE VERDAD para qué tareas se consideran en el análisis.
        """
        self.ensure_one()
        if not self.project_ids:
            return self.env['project.task']

        domain = [('project_id', 'in', self.project_ids.ids)]

        if self.ubicacion_ids:
            domain.append(
                ('project_id.ubicacion', 'in', self.ubicacion_ids.ids))

        context = self.env.context.copy()
        if self.include_archived:
            context['active_test'] = False
            Task = self.env['project.task'].with_context(context)
        else:
            Task = self.env['project.task']

        if self.filter_type == 'filter' and self.task_ids:
            return self.task_ids

        if self.task_state_filter == 'all':
            domain.append(('state', '!=', '1_canceled'))
        elif self.task_state_filter:
            domain.append(('state', '=', self.task_state_filter))

        return Task.search(domain)

    # =========================================================================
    # SECCIÓN: LÓGICA DE VENTAS (INGRESOS)
    # =========================================================================

    def _get_sale_order_lines(self):
        """
        Obtiene las líneas de venta relacionadas al proyecto.
        """
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # FIX 4 — Guardia defensiva: si no hay tareas ni proyectos, retornar vacío
        # para evitar que link_domain quede vacío y devuelva registros globales.
        projects = self._get_filtered_projects()
        if not all_tasks and not projects:
            return self.env['sale.order.line']

        final_domain = [('state', 'in', ['sale', 'done'])]

        if self.date_filter_type != 'none':
            if self.date_from:
                final_domain.append(
                    ('order_id.date_order', '>=', self.date_from))
            if self.date_to:
                final_domain.append(
                    ('order_id.date_order', '<=', self.date_to))

        # 1. Tarea
        domain_task = [('task_id', 'in', all_tasks.ids)]

        # 2. Proyecto — FIX 2: omitir cuando hay filtro de estado activo para no
        #    mezclar registros de proyecto que eludan el filtro de tareas.
        domain_project = []
        if projects and not self._has_task_state_filter():
            parts = [('order_id.project_id', 'in', projects.ids)]
            if 'project_id' in self.env['sale.order.line']._fields:
                parts.append(('project_id', 'in', projects.ids))
            domain_project = expression.OR([[p] for p in parts])

        # 3. Bloque Analítico
        domain_analytic = self._build_analytic_domain(
            'sale.order.line', projects)
        _logger.info('[SOL] include_analytic_account=%s | analytics ids=%s',
                     self.include_analytic_account,
                     projects.mapped('analytic_account_id').ids if projects else [])
        _logger.info('[SOL] Campo analytic_distribution en SOL: %s',
                     'analytic_distribution' in self.env['sale.order.line']._fields)

        link_parts = [p for p in [domain_task, domain_project, domain_analytic] if p]

        # FIX 4 — Si no hay partes de vinculación, retornar vacío (nunca buscar global)
        if not link_parts:
            return self.env['sale.order.line']

        link_domain = expression.OR(link_parts)
        full_domain = expression.AND([final_domain, link_domain])

        _logger.info('[SOL] === DOMINIO FINAL _get_sale_order_lines ===')
        for i, leaf in enumerate(full_domain):
            _logger.info('[SOL]   [%d] %s', i, leaf)

        return self.env['sale.order.line'].search(full_domain)

    def _get_sale_orders(self):
        """Retorna las órdenes de venta distintas derivadas de las líneas."""
        return self._get_sale_order_lines().mapped('order_id')

    def _get_related_invoices(self):
        """
        Obtiene las facturas de cliente (account.move, tipo out_invoice) vinculadas
        a las órdenes de venta derivadas de las líneas de venta filtradas.
        """
        self.ensure_one()
        sale_lines = self._get_sale_order_lines()
        if not sale_lines:
            return self.env['account.move']
        all_invoices = sale_lines.mapped('order_id.invoice_ids')
        return all_invoices.filtered(
            lambda inv: inv.move_type == 'out_invoice'
        )

    # =========================================================================
    # SECCIÓN: LÓGICA DE COMPRAS
    # =========================================================================

    def _get_purchase_order_lines(self):
        """
        Obtiene líneas de compra comprometidas o realizadas.
        """
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # FIX 4 — Guardia defensiva
        projects = self._get_filtered_projects()
        if not all_tasks and not projects:
            return self.env['purchase.order.line']

        final_domain = [('order_id.state', 'in', ['purchase', 'done'])]

        if self.date_filter_type != 'none':
            if self.date_from:
                final_domain.append(
                    ('order_id.date_order', '>=', self.date_from))
            if self.date_to:
                final_domain.append(
                    ('order_id.date_order', '<=', self.date_to))

        # 1. Tarea
        domain_task = [('task_id', 'in', all_tasks.ids)]

        # 2. Proyecto — FIX 2: omitir cuando hay filtro de estado activo
        domain_project = []
        if projects and not self._has_task_state_filter():
            parts = [('order_id.project_id', 'in', projects.ids)]
            if 'project_id' in self.env['purchase.order.line']._fields:
                parts.append(('project_id', 'in', projects.ids))
            domain_project = expression.OR([[p] for p in parts])

        # 3. Bloque Analítico
        domain_analytic = self._build_analytic_domain(
            'purchase.order.line', projects)
        _logger.info('[POL] include_analytic_account=%s | analytics ids=%s',
                     self.include_analytic_account,
                     projects.mapped('analytic_account_id').ids if projects else [])
        _logger.info('[POL] Campo analytic_distribution en POL: %s',
                     'analytic_distribution' in self.env['purchase.order.line']._fields)

        link_parts = [p for p in [domain_task, domain_project, domain_analytic] if p]

        # FIX 4 — Guardia: sin partes de vínculo → vacío
        if not link_parts:
            return self.env['purchase.order.line']

        link_domain = expression.OR(link_parts)
        full_domain = expression.AND([final_domain, link_domain])

        _logger.info('[POL] === DOMINIO FINAL _get_purchase_order_lines ===')
        for i, leaf in enumerate(full_domain):
            _logger.info('[POL]   [%d] %s', i, leaf)

        return self.env['purchase.order.line'].search(full_domain)

    def _get_purchase_orders(self):
        return self._get_purchase_order_lines().mapped('order_id')

    # =========================================================================
    # SECCIÓN: LÓGICA DE STOCK Y MOVIMIENTOS
    # =========================================================================

    def _get_stock_moves(self):
        """Retorna los Movimientos de Almacén específicos vinculados al proyecto."""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # FIX 4 — Guardia defensiva
        projects = self._get_filtered_projects()
        if not all_tasks and not projects:
            return self.env['stock.move']

        final_domain = [('state', '=', 'done')]

        if self.date_filter_type != 'none':
            if self.date_from:
                final_domain.append(('date', '>=', self.date_from))
            if self.date_to:
                final_domain.append(('date', '<=', self.date_to))

        # 1. Tarea
        domain_task = [('task_id', 'in', all_tasks.ids)]

        # 2. Proyecto — FIX 2: omitir cuando hay filtro de estado activo
        domain_project = []
        if projects and not self._has_task_state_filter():
            parts = [('picking_id.project_id', 'in', projects.ids)]
            if 'project_id' in self.env['stock.move']._fields:
                parts.append(('project_id', 'in', projects.ids))
            domain_project = expression.OR([[p] for p in parts])

        link_parts = [p for p in [domain_task, domain_project] if p]

        # FIX 4 — Guardia: sin partes de vínculo → vacío
        if not link_parts:
            return self.env['stock.move']

        link_domain = expression.OR(link_parts)
        full_domain = expression.AND([final_domain, link_domain])

        return self.env['stock.move'].search(full_domain)

    # =========================================================================
    # SECCIÓN: LÓGICA DE HOJAS DE HORAS (TIMESHEETS)
    # =========================================================================

    def _get_timesheets(self):
        """
        Retorna las líneas analíticas (horas) asociadas al proyecto.
        """
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        # FIX 5 — Guardia defensiva: si no hay proyectos, retornar vacío
        # para evitar que un domain=[] devuelva TODOS los timesheets del sistema.
        projects = self._get_filtered_projects()
        if not projects:
            return self.env['account.analytic.line']

        domain = [('project_id', 'in', projects.ids)]

        # FIX 2 — Si hay filtro de estado, forzar también el filtro por tareas
        # para que las horas de tareas en otros estados no se cuenten.
        if self.task_ids or self._has_task_state_filter():
            domain.append(('task_id', 'in', all_tasks.ids))

        if self.date_filter_type != 'none':
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<=', self.date_to))

        return self.env['account.analytic.line'].sudo().search(domain)

    # =========================================================================
    # SECCIÓN: LÓGICA DE COMPENSACIONES
    # =========================================================================

    def _get_compensations(self):
        """Obtiene líneas de compensación (nómina/extras) en estado Aplicado."""
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        domain = [('compensation_id.state', '=', 'applied')]

        has_project = 'project_id' in self.env['compensation.line']._fields
        if has_project:
            projects = self._get_filtered_projects()
            # FIX 2/3 — Si hay filtro de estado, usar solo tareas
            if self._has_task_state_filter():
                domain.append(('task_id', 'in', all_tasks.ids))
            else:
                domain += ['|',
                           ('task_id', 'in', all_tasks.ids),
                           '&',
                           ('project_id', 'in', projects.ids),
                           ('task_id', '=', False)]
        else:
            domain.append(('task_id', 'in', all_tasks.ids))

        date_field = 'date' if 'date' in self.env['compensation.line']._fields else 'create_date'

        if self.date_filter_type != 'none':
            if self.date_from:
                domain.append((date_field, '>=', self.date_from))
            if self.date_to:
                domain.append((date_field, '<=', self.date_to))

        return self.env['compensation.line'].search(domain)

    # =========================================================================
    # HELPERS DE CONVERSIÓN MASIVA (Anti N+1)
    # =========================================================================

    def _convert_grouped_by_currency(self, records, amount_getter, date_getter, target_currency):
        """
        Convierte montos de un recordset agrupando por (currency_id, fecha) para minimizar
        llamadas a la API de tipos de cambio (evita el problema N+1).
        """
        groups = defaultdict(float)
        company = self.env.company

        for rec in records:
            amount = amount_getter(rec)
            if not amount:
                continue
            src_curr = rec.currency_id if rec.currency_id else self.env.company.currency_id
            doc_date = date_getter(rec) or fields.Date.context_today(self)
            if hasattr(doc_date, 'date'):
                doc_date = doc_date.date()
            groups[(src_curr.id, doc_date)] += amount

        currencies = {
            c.id: c for c in self.env['res.currency'].browse(
                list({cid for cid, _ in groups})
            )
        }

        total = 0.0
        for (cid, doc_date), amount in groups.items():
            src_curr = currencies.get(cid, target_currency)
            total += amount if src_curr == target_currency else src_curr._convert(
                amount, target_currency, company, doc_date)
        return total

    def _get_stock_valuation_bulk(self, stock_moves):
        """
        Búsqueda masiva de capas de valoración para un conjunto de movimientos.
        Evita acceder a move.stock_valuation_layer_ids dentro de un bucle (N+1).
        """
        if not stock_moves:
            return {}
        layers = self.env['stock.valuation.layer'].sudo().search([
            ('stock_move_id', 'in', stock_moves.ids)
        ])
        result = defaultdict(float)
        for layer in layers:
            result[layer.stock_move_id.id] += abs(layer.value)
        return result

    # =========================================================================
    # SECCIÓN: CÁLCULO DE RENTABILIDAD
    # =========================================================================

    def _get_profitability_data(self, projects, date_from, date_to):
        """
        Calcula la rentabilidad para un set de proyectos en un rango de fechas.
        """
        if not projects:
            return defaultdict(float)

        target_currency = self.currency_id
        company_currency = self.env.company.currency_id
        company = self.env.company

        def convert(amount, src_curr, date):
            return self._convert_amount(amount, src_curr, target_currency, date)

        def get_date_domain(field_name):
            d_dom = []
            if date_from:
                d_dom.append((field_name, '>=', date_from))
            if date_to:
                d_dom.append((field_name, '<=', date_to))
            return d_dom

        # ── A. INGRESOS ──────────────────────────────────────────────────────
        sols = self._get_sale_order_lines()

        expected = self._convert_grouped_by_currency(
            sols,
            amount_getter=lambda s: s.price_subtotal,
            date_getter=lambda s: s.order_id.date_order,
            target_currency=target_currency,
        )

        inv_domain = [('move_id.state', '=', 'posted')] + \
            get_date_domain('move_id.invoice_date')
        posted_lines = sols.mapped('invoice_lines').filtered_domain(inv_domain)
        invoiced = self._convert_grouped_by_currency(
            posted_lines,
            amount_getter=lambda l: l.price_subtotal,
            date_getter=lambda l: l.move_id.invoice_date,
            target_currency=target_currency,
        )

        to_invoice = 0.0
        to_inv_groups = defaultdict(float)
        for sol in sols:
            qty_to_inv = sol.qty_to_invoice
            if qty_to_inv > 0:
                src_curr_id = sol.currency_id.id
                doc_date = sol.order_id.date_order
                if hasattr(doc_date, 'date'):
                    doc_date = doc_date.date()
                to_inv_groups[(src_curr_id, doc_date)
                              ] += qty_to_inv * sol.price_unit

        currencies_cache = {
            c.id: c for c in self.env['res.currency'].browse(
                list({cid for cid, _ in to_inv_groups})
            )
        }
        for (cid, doc_date), amount in to_inv_groups.items():
            src_curr = currencies_cache.get(cid, target_currency)
            to_invoice += amount if src_curr == target_currency else src_curr._convert(
                amount, target_currency, company, doc_date)

        # ── B. GASTOS ─────────────────────────────────────────────────────────
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        expense_domain = self._get_expense_domain(all_tasks)
        expenses = self.env['hr.expense'].sudo().search(expense_domain)

        _exp_amount_field = self._get_expense_amount_field()

        def _expense_amount(exp):
            if _exp_amount_field:
                return getattr(exp, _exp_amount_field, 0.0) or 0.0
            return getattr(exp, 'total_amount_currency', 0.0) or exp.total_amount

        sheet_model = self.env['hr.expense.sheet']
        sheet_fields = sheet_model._fields

        if 'account_move_id' in sheet_fields:
            expenses.mapped('sheet_id.account_move_id.state')
            exp_billed = expenses.filtered(
                lambda e: e.sheet_id.account_move_id
                          and e.sheet_id.account_move_id.state == 'posted'
            )
        elif 'account_move_ids' in sheet_fields:
            expenses.mapped('sheet_id.account_move_ids.state')
            exp_billed = expenses.filtered(
                lambda e: any(
                    m.state == 'posted'
                    for m in e.sheet_id.account_move_ids
                )
            )
        elif 'move_id' in sheet_fields:
            expenses.mapped('sheet_id.move_id.state')
            exp_billed = expenses.filtered(
                lambda e: e.sheet_id.move_id
                          and e.sheet_id.move_id.state == 'posted'
            )
        else:
            exp_billed = expenses.filtered(
                lambda e: e.sheet_id.state in ('post', 'done')
            )

        exp_to_bill = expenses - exp_billed

        exp_billed_total = self._convert_grouped_by_currency(
            exp_billed, _expense_amount, lambda e: e.date, target_currency)
        exp_to_bill_total = self._convert_grouped_by_currency(
            exp_to_bill, _expense_amount, lambda e: e.date, target_currency)
        total_expenses = exp_billed_total + exp_to_bill_total

        # ── C. COMPRAS ────────────────────────────────────────────────────────
        purchase_lines = self._get_purchase_order_lines()

        p_billed_groups   = defaultdict(float)
        p_to_bill_groups  = defaultdict(float)
        p_total_groups    = defaultdict(float)

        for pl in purchase_lines:
            qty_invoiced   = pl.qty_invoiced or 0.0
            qty_received   = pl.qty_received or 0.0
            qty_to_bill    = max(0.0, qty_received - qty_invoiced)
            price          = pl.price_unit   or 0.0
            price_subtotal = pl.price_subtotal or 0.0

            date_doc = pl.order_id.date_order
            if hasattr(date_doc, 'date'):
                date_doc = date_doc.date()

            key = (pl.currency_id.id, date_doc)

            if qty_invoiced:
                p_billed_groups[key]  += qty_invoiced * price
            if qty_to_bill:
                p_to_bill_groups[key] += qty_to_bill * price
            if price_subtotal:
                p_total_groups[key]   += price_subtotal

        all_pur_cids = list({cid for cid, _ in
                             list(p_billed_groups) +
                             list(p_to_bill_groups) +
                             list(p_total_groups)})
        pur_currencies = {c.id: c
                          for c in self.env['res.currency'].browse(all_pur_cids)}

        def _conv_groups(groups):
            total = 0.0
            for (cid, doc_date), amount in groups.items():
                src = pur_currencies.get(cid, target_currency)
                total += (amount if src == target_currency
                          else src._convert(amount, target_currency, company, doc_date))
            return total

        p_billed       = _conv_groups(p_billed_groups)
        p_to_bill_pur  = _conv_groups(p_to_bill_groups)
        total_purchases = _conv_groups(p_total_groups)

        p_incurred  = p_billed + p_to_bill_pur
        p_committed = total_purchases - p_incurred

        # ── D. STOCK ─────────────────────────────────────────────────────────
        stock_moves = self._get_stock_moves()
        valid_moves = self._filter_non_purchase_moves(stock_moves)

        valid_moves.mapped('location_id.usage')
        valid_moves.mapped('location_dest_id.usage')

        layer_values = self._get_stock_valuation_bulk(valid_moves)

        moves_with_posted_account = set()
        if valid_moves:
            svl_model = self.env['stock.valuation.layer']
            svl_fields = svl_model._fields
            if 'account_move_id' in svl_fields:
                svl_posted = svl_model.sudo().search([
                    ('stock_move_id', 'in', valid_moves.ids),
                    ('account_move_id', '!=', False),
                    ('account_move_id.state', '=', 'posted'),
                ])
                moves_with_posted_account = set(svl_posted.mapped('stock_move_id.id'))
            else:
                valuation_method = self.env.company.sudo().property_cost_method
                auto_accounting = (valuation_method in ('average', 'fifo'))
                if auto_accounting:
                    moves_with_posted_account = set(valid_moves.ids)

        stock_billed_out   = defaultdict(float)
        stock_billed_in    = defaultdict(float)
        stock_to_bill_out  = defaultdict(float)
        stock_to_bill_in   = defaultdict(float)

        for move in valid_moves:
            total_val = layer_values.get(move.id)
            if total_val is None:
                val_unit = move.price_unit or move.product_id.standard_price
                qty = move.quantity if move.state == 'done' else move.product_uom_qty
                total_val = val_unit * qty

            is_outgoing = (move.location_id.usage == 'internal'
                           and move.location_dest_id.usage != 'internal')
            is_return   = (move.location_id.usage != 'internal'
                           and move.location_dest_id.usage == 'internal')

            doc_date = move.date
            if hasattr(doc_date, 'date'):
                doc_date = doc_date.date()

            has_accounting = move.id in moves_with_posted_account

            if is_outgoing:
                if has_accounting:
                    stock_billed_out[doc_date]  += total_val
                else:
                    stock_to_bill_out[doc_date] += total_val
            elif is_return:
                if has_accounting:
                    stock_billed_in[doc_date]   += total_val
                else:
                    stock_to_bill_in[doc_date]  += total_val

        stock_billed_val = (
            sum(convert(v, company_currency, d) for d, v in stock_billed_out.items())
            - sum(convert(v, company_currency, d) for d, v in stock_billed_in.items())
        )
        stock_to_bill_val = (
            sum(convert(v, company_currency, d) for d, v in stock_to_bill_out.items())
            - sum(convert(v, company_currency, d) for d, v in stock_to_bill_in.items())
        )
        stock_cost = stock_billed_val + stock_to_bill_val

        # ── E. MANO DE OBRA ──────────────────────────────────────────────────
        timesheets = self._get_timesheets()

        timesheet_cost = self._convert_grouped_by_currency(
            timesheets,
            amount_getter=lambda ts: abs(ts.amount),
            date_getter=lambda ts: ts.date,
            target_currency=target_currency,
        )
        ts_billed_cost  = timesheet_cost
        ts_to_bill_cost = 0.0

        self._get_compensations()

        # ── TOTALES ──────────────────────────────────────────────────────────
        total_costs_real = total_expenses + total_purchases + stock_cost + timesheet_cost
        margin_total = invoiced - total_costs_real

        profit_percentage = 0.0
        if invoiced:
            profit_percentage = (margin_total / invoiced) * 100.0
        elif expected:
            profit_percentage = (margin_total / expected) * 100.0

        return {
            # Ingresos
            'expected_income':   expected,
            'invoiced_income':   invoiced,
            'to_invoice_income': to_invoice,
            # Gastos
            'total_expenses':    total_expenses,
            'expenses_billed':   exp_billed_total,
            'expenses_to_bill':  exp_to_bill_total,
            # Compras
            'total_purchases':   total_purchases,
            'purchases_billed':  p_billed,
            'purchases_to_bill': p_to_bill_pur,
            'purchase_incurred': p_incurred,
            'purchase_committed': p_committed,
            # Stock
            'total_stock_moves': stock_cost,
            'stock_billed':      stock_billed_val,
            'stock_to_bill':     stock_to_bill_val,
            # Timesheets
            'timesheet_cost':    timesheet_cost,
            'timesheet_billed':  ts_billed_cost,
            'timesheet_to_bill': ts_to_bill_cost,
            # Totales
            'margin_total':      margin_total,
            'profit_percentage': profit_percentage,
            'total_costs':       total_costs_real,
        }

    # FIX 1 — @api.depends agregado para que Odoo recalcule los KPIs
    # automáticamente al cambiar cualquier filtro (no solo en onchange UI).
    @api.depends(
        'project_ids', 'filter_type', 'task_ids', 'task_state_filter',
        'date_filter_type', 'date_from', 'date_to', 'include_archived',
        'ubicacion_ids', 'include_analytic_account',
    )
    def _compute_profitability(self):
        for wizard in self:
            data = wizard._get_profitability_data(
                wizard.project_ids, wizard.date_from, wizard.date_to)

            wizard.expected_income   = data['expected_income']
            wizard.invoiced_income   = data['invoiced_income']
            wizard.to_invoice_income = data['to_invoice_income']
            wizard.total_expenses    = data['total_expenses']
            wizard.expenses_billed   = data['expenses_billed']
            wizard.expenses_to_bill  = data['expenses_to_bill']
            wizard.total_purchases   = data['total_purchases']
            wizard.purchases_billed  = data['purchases_billed']
            wizard.purchases_to_bill = data['purchases_to_bill']
            wizard.purchase_cost_incurred = data['purchase_incurred']
            wizard.purchase_committed     = data['purchase_committed']
            wizard.total_stock_moves = data['total_stock_moves']
            wizard.stock_billed      = data['stock_billed']
            wizard.stock_to_bill     = data['stock_to_bill']
            wizard.timesheet_cost    = data['timesheet_cost']
            wizard.timesheet_billed  = data['timesheet_billed']
            wizard.timesheet_to_bill = data['timesheet_to_bill']
            wizard.margin_total      = data['margin_total']
            wizard.profit_percentage = data['profit_percentage']

    # =========================================================================
    # SECCIÓN: LÓGICA DE GASTOS (EXPENSES)
    # =========================================================================

    def _get_expense_domain(self, all_tasks):
        """
        Construye el dominio para buscar gastos.
        """
        self.ensure_one()

        projects = self._get_filtered_projects()

        # FIX 4 — Guardia defensiva: sin tareas ni proyectos → dominio vacío
        if not all_tasks and not projects:
            return [('id', '=', False)]

        # 1. Tarea
        domain_task = [('task_id', 'in', all_tasks.ids)]

        # 2. Proyecto — FIX 2: omitir cuando hay filtro de estado activo
        domain_project = []
        if 'project_id' in self.env['hr.expense']._fields and not self._has_task_state_filter():
            domain_project = [('project_id', 'in', projects.ids)]

        # 3. Bloque Analítico
        domain_analytic = self._build_analytic_domain('hr.expense', projects)
        _logger.info('[EXP] include_analytic_account=%s | analytics ids=%s',
                     self.include_analytic_account,
                     projects.mapped('analytic_account_id').ids if projects else [])
        _logger.info('[EXP] Campo analytic_distribution en hr.expense: %s',
                     'analytic_distribution' in self.env['hr.expense']._fields)

        link_parts = [p for p in [domain_task, domain_project, domain_analytic] if p]

        # FIX 4 — Guardia: sin partes → dominio que no devuelve nada
        if not link_parts:
            return [('id', '=', False)]

        link_domain = expression.OR(link_parts)

        state_domain = [('sheet_id.state', 'in', ['approve', 'post', 'done'])]
        date_domain = self._get_date_domain('date')

        domain = expression.AND(
            [link_domain, state_domain] + ([date_domain] if date_domain else []))

        _logger.info('[EXP] === DOMINIO FINAL _get_expense_domain ===')
        for i, leaf in enumerate(domain):
            _logger.info('[EXP]   [%d] %s', i, leaf)
        return domain

    # =========================================================================
    # SECCIÓN: COMPUTE CONTENT (orquestador limpio)
    # =========================================================================

    @api.depends(
        'project_ids', 'filter_type', 'task_ids', 'task_state_filter',
        'date_filter_type', 'date_from', 'date_to', 'chart_type',
        'ubicacion_ids', 'include_archived',
    )
    def _compute_content(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            all_tasks = tasks | tasks.mapped('child_ids')

            values = {
                'wizard': wizard,
                'stock_moves_list': wizard._prepare_stock_display_data(),
                'purchases_list': wizard._prepare_purchase_display_data(),
                'expenses_list': wizard._prepare_expense_display_data(all_tasks),
                'timesheets_list': wizard._prepare_timesheet_display_data(),
                'chart_data': wizard._prepare_pie_chart_data(),
                'column_data': wizard._prepare_waterfall_data(),
                'line_chart_svg': wizard._generate_line_chart_svg(all_tasks),
                **wizard._compute_alerts(),
                'kpis': {
                    'purchase_committed': wizard.purchase_committed,
                    'purchase_incurred': wizard.purchase_cost_incurred,
                },
                'profitability': {
                    'expected_income':    wizard.expected_income,
                    'invoiced_income':    wizard.invoiced_income,
                    'to_invoice_income':  wizard.to_invoice_income,
                    'total_expenses':     wizard.total_expenses,
                    'expenses_billed':    wizard.expenses_billed,
                    'expenses_to_bill':   wizard.expenses_to_bill,
                    'total_purchases':    wizard.total_purchases,
                    'purchases_billed':   wizard.purchases_billed,
                    'purchases_to_bill':  wizard.purchases_to_bill,
                    'purchase_incurred':  wizard.purchase_cost_incurred,
                    'purchase_committed': wizard.purchase_committed,
                    'total_stock_moves':  wizard.total_stock_moves,
                    'stock_billed':       wizard.stock_billed,
                    'stock_to_bill':      wizard.stock_to_bill,
                    'timesheet_cost':     wizard.timesheet_cost,
                    'timesheet_billed':   wizard.timesheet_billed,
                    'timesheet_to_bill':  wizard.timesheet_to_bill,
                    'margin_total':       wizard.margin_total,
                    'profit_percentage':  wizard.profit_percentage,
                    'total_costs': (
                        wizard.total_expenses + wizard.total_purchases
                        + wizard.total_stock_moves + wizard.timesheet_cost
                    ),
                },
                'format_monetary': lambda v: format_amount(
                    self.env, float_round(v, precision_digits=2), wizard.currency_id),
                'format_percentage': lambda v: f"{v:.2f}%",
            }

            wizard.content = self.env['ir.qweb']._render(
                'project_modificaciones.project_profitability_template', values)

    # ── Sub-métodos de preparación de datos para la vista ───────────────────

    def _prepare_stock_display_data(self):
        """Prepara la lista de movimientos de stock para la vista."""
        moves = self._get_stock_moves().sorted('date', reverse=True)
        valid_moves = self._filter_non_purchase_moves(moves)

        valid_moves.mapped('location_id.usage')
        valid_moves.mapped('location_dest_id.usage')
        valid_moves.mapped('product_id.display_name')
        valid_moves.mapped('task_id.name')
        valid_moves.mapped('picking_id.name')

        layer_values = self._get_stock_valuation_bulk(valid_moves)
        company_currency = self.env.company.currency_id
        target_currency = self.currency_id
        base_url = self.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')

        state_map = {
            'draft': 'Borrador', 'waiting': 'Esperando', 'confirmed': 'En espera',
            'assigned': 'Reservado', 'done': 'Hecho', 'cancel': 'Cancelado',
        }

        result = []
        for move in valid_moves:
            total_val = layer_values.get(move.id)
            if total_val is None:
                val_unit = move.price_unit or move.product_id.standard_price
                qty_fb = move.quantity if move.state == 'done' else move.product_uom_qty
                total_val = val_unit * qty_fb

            total_cost = self._convert_amount(
                total_val, company_currency, target_currency, move.date)

            is_outgoing = (move.location_id.usage == 'internal'
                           and move.location_dest_id.usage != 'internal')
            is_return = (move.location_id.usage != 'internal'
                         and move.location_dest_id.usage == 'internal')

            move_label = move.reference
            if is_return:
                total_cost = -total_cost
            elif not is_outgoing:
                total_cost = 0.0
                move_label = f"{move.reference} (Resguardo / Interno)"

            qty_display = move.quantity if move.state == 'done' else move.product_uom_qty
            unit_cost_display = abs(
                total_cost / qty_display) if qty_display else 0.0

            result.append({
                'product_name': move.product_id.display_name,
                'task_name': move.task_id.name or '-',
                'project_name': move.task_id.project_id.name or move.project_id.name,
                'date': move.date,
                'quantity': qty_display,
                'uom': move.product_uom.name,
                'reference': move_label,
                'picking': move.picking_id.name,
                'picking_url': f"{base_url}/web#id={move.id}&model=stock.move&view_type=form",
                'price_unit': unit_cost_display,
                'total_cost': total_cost,
                'state_label': state_map.get(move.state, move.state),
                'state_raw': move.state,
                'location_id': move.location_id.display_name,
                'location_dest_id': move.location_dest_id.display_name,
                'lot_name': ", ".join(move.move_line_ids.mapped('lot_id.name')) or "-",
            })
        return result

    def _prepare_purchase_display_data(self):
        """Prepara la lista de líneas de compra para la vista."""
        target_currency = self.currency_id
        purchase_lines = self._get_purchase_order_lines().sorted('create_date', reverse=True)

        state_map = {
            'draft': 'Borrador', 'sent': 'Enviado', 'to approve': 'Por Aprobar',
            'purchase': 'Pedido Compra', 'done': 'Bloqueado', 'cancel': 'Cancelado',
        }

        return [
            {
                'order_name': line.order_id.name,
                'order_id': line.order_id.id,
                'project_name': line.task_id.project_id.name or line.project_id.name,
                'task_name': line.task_id.name or '-',
                'purchase_order_model': 'purchase.order',
                'date': line.date_order,
                'partner': line.partner_id.name,
                'product': line.product_id.display_name,
                'qty': line.product_qty,
                'price_unit': line.price_unit,
                'total': self._convert_amount(
                    line.price_subtotal, line.currency_id, target_currency, line.order_id.date_order),
                'currency': target_currency.symbol,
                'state': state_map.get(line.order_id.state, line.order_id.state),
                'state_raw': line.order_id.state,
            }
            for line in purchase_lines
        ]

    def _prepare_expense_display_data(self, all_tasks):
        """Prepara la lista de gastos para la vista."""
        target_currency = self.currency_id
        exp_domain = self._get_expense_domain(all_tasks)
        expenses = self.env['hr.expense'].sudo().search(
            exp_domain, order='date desc')

        state_map = {
            'draft': 'Borrador', 'reported': 'Enviado', 'approved': 'Aprobado',
            'post': 'Publicado', 'done': 'Pagado', 'refused': 'Rechazado',
        }

        _amount_field = self._get_expense_amount_field()
        _has_project_field = 'project_id' in self.env['hr.expense']._fields

        def get_amount(exp):
            if _amount_field:
                return getattr(exp, _amount_field, 0.0) or 0.0
            return getattr(exp, 'total_amount_currency', 0.0) or exp.total_amount

        return [
            {
                'name': exp.name,
                'employee': exp.employee_id.name,
                'project_name': (exp.task_id.project_id.name or exp.project_id.name)
                if _has_project_field else '-',
                'task_name': exp.task_id.name or '-',
                'date': exp.date,
                'product': exp.product_id.display_name,
                'total': self._convert_amount(get_amount(exp), exp.currency_id, target_currency, exp.date),
                'currency': target_currency.symbol,
                'state': state_map.get(exp.state, exp.state),
                'state_raw': exp.state,
                'sheet_name': exp.sheet_id.name,
                'exp_url': f"/web#id={exp.id}&model=hr.expense&view_type=form",
            }
            for exp in expenses
        ]

    def _prepare_timesheet_display_data(self):
        """Prepara la lista de timesheets para la vista."""
        timesheets = self._get_timesheets().sorted('date', reverse=True)
        timesheets.mapped('employee_id.name')
        timesheets.mapped('project_id.name')
        timesheets.mapped('task_id.name')

        return [
            {
                'employee': al.employee_id.name,
                'project_name': al.project_id.name,
                'date': al.date,
                'description': al.name,
                'task': al.task_id.name or '-',
                'total': -al.amount,
                'currency': al.currency_id.symbol,
                'state_label': 'Validado',
                'state_raw': 'validated',
                'ts_url': f"/web#id={al.id}&model=account.analytic.line&view_type=form",
            }
            for al in timesheets
        ]

    def _prepare_invoice_display_data(self):
        """
        Serializa las facturas de cliente relacionadas en dicts listos para
        el template QWeb del PDF.
        """
        self.ensure_one()
        invoices = self._get_related_invoices().sorted(
            key=lambda inv: inv.invoice_date or date.min,
            reverse=True,
        )
        if not invoices:
            return []

        invoices.mapped('partner_id.name')

        target_currency = self.currency_id

        state_label_map = {
            'draft':  'Borrador',
            'posted': 'Publicada',
            'cancel': 'Cancelada',
        }
        payment_state_label_map = {
            'not_paid':         'No Pagada',
            'in_payment':       'En Pago',
            'paid':             'Pagada',
            'partial':          'Pago Parcial',
            'reversed':         'Revertida',
            'invoicing_legacy': 'Pagada',
        }

        result = []
        for inv in invoices:
            inv_currency = inv.currency_id or self.env.company.currency_id
            inv_date = inv.invoice_date or fields.Date.context_today(self)

            def _conv(amount, _ic=inv_currency, _id=inv_date):
                return self._convert_amount(amount, _ic, target_currency, _id)

            raw_state = inv.state
            payment_state = getattr(inv, 'payment_state', 'not_paid') or 'not_paid'

            if raw_state == 'posted' and payment_state == 'paid':
                display_state = 'Pagada'
            elif raw_state == 'posted':
                display_state = payment_state_label_map.get(payment_state, 'Publicada')
            else:
                display_state = state_label_map.get(raw_state, raw_state)

            result.append({
                'id':               inv.id,
                'name':             inv.name or '/',
                'partner':          inv.partner_id.name or '—',
                'invoice_date':     inv.invoice_date,
                'invoice_date_due': inv.invoice_date_due,
                'amount_untaxed':   _conv(inv.amount_untaxed),
                'amount_tax':       _conv(inv.amount_tax),
                'amount_total':     _conv(inv.amount_total),
                'amount_residual':  _conv(inv.amount_residual),
                'state':            raw_state,
                'payment_state':    payment_state,
                'state_label':      display_state,
            })

        return result

    def _prepare_pie_chart_data(self):
        """
        Calcula proporciones para el gráfico de torta de costos.
        Retorna 0% explícitamente cuando no hay costos.
        """
        total = (self.total_stock_moves + self.total_purchases
                 + self.timesheet_cost + self.total_expenses)

        if not total:
            return {'stock_pct': 0, 'purchases_pct': 0, 'timesheets_pct': 0,
                    'expenses_pct': 0, 'style': ''}

        p_stock = (self.total_stock_moves / total) * 100
        p_purchases = (self.total_purchases / total) * 100
        p_timesheets = (self.timesheet_cost / total) * 100
        p_expenses = (self.total_expenses / total) * 100

        c_stock = f"#dc3545 0% {p_stock:.2f}%"
        c_purch = f"#0d6efd {p_stock:.2f}% {p_stock + p_purchases:.2f}%"
        c_time = f"#fd7e14 {p_stock + p_purchases:.2f}% {p_stock + p_purchases + p_timesheets:.2f}%"
        c_exp = f"#6610f2 {p_stock + p_purchases + p_timesheets:.2f}% 100%"

        return {
            'stock_pct': p_stock,
            'purchases_pct': p_purchases,
            'timesheets_pct': p_timesheets,
            'expenses_pct': p_expenses,
            'style': (f"width:100%;height:100%;border-radius:50%;"
                      f"background:conic-gradient({c_stock},{c_purch},{c_time},{c_exp});"),
        }

    def _prepare_waterfall_data(self):
        """Prepara los datos para el gráfico de cascada de rentabilidad."""
        if self.chart_type != 'waterfall':
            return []

        rev = self.invoiced_income
        exp = -self.total_expenses
        pur_total = -self.total_purchases
        stk = -self.total_stock_moves
        tsh = -self.timesheet_cost
        final_margin = rev + exp + pur_total + stk + tsh

        steps = [
            {'label': 'Ingresos', 'val': rev, 'color': '#198754', 'is_total': False},
            {'label': 'Gastos', 'val': exp, 'color': '#6f42c1', 'is_total': False},
            {'label': 'Compras', 'val': pur_total, 'color': '#0d6efd', 'is_total': False},
            {'label': 'Stock', 'val': stk, 'color': '#dc3545', 'is_total': False},
            {'label': 'Mano de Obra', 'val': tsh, 'color': '#fd7e14', 'is_total': False},
            {'label': 'Margen Final', 'val': final_margin, 'color': '#20c997', 'is_total': True},
        ]

        running = 0.0
        peaks = [0.0]
        for step in steps:
            running = step['val'] if step['label'] == 'Ingresos' else running + step['val']
            peaks.extend([running, abs(step['val'])])
        max_val = max(peaks + [rev]) * 1.1 or 1.0

        column_data = []
        current_y = 0.0

        for step in steps:
            val = step['val']
            if step['label'] == 'Ingresos':
                y_start, y_end, current_y = 0, val, val
            elif step['is_total']:
                y_start, y_end = 0, current_y
            else:
                y_start = current_y
                y_end = current_y + val
                current_y = y_end

            column_data.append({
                'label': step['label'],
                'amount': val,
                'bottom': (min(y_start, y_end) / max_val) * 100.0,
                'height': (abs(val) / max_val) * 100.0,
                'color': step['color'],
                'is_negative': val < 0,
            })

        return column_data

    def _compute_alerts(self):
        """Evalúa alertas de rentabilidad y retorna un dict listo para el contexto QWeb."""
        alert_negative_profit = self.margin_total < 0
        alert_low_margin = (
            not alert_negative_profit
            and self.profit_percentage < 10.0
            and self.invoiced_income > 0
        )
        return {
            'alert_negative_profit': alert_negative_profit,
            'alert_low_margin': alert_low_margin,
        }

    def _generate_line_chart_svg(self, all_tasks):
        """
        Genera el SVG del gráfico de evolución temporal acumulada (S-Curve).
        Retorna Markup vacío si chart_type no es 'line' o no hay datos.
        """
        if self.chart_type != 'line':
            return Markup('')

        target_currency = self.currency_id
        company_currency = self.env.company.currency_id

        sols = all_tasks.mapped('sale_line_id')
        timesheets = self._get_timesheets()
        expenses_domain = self._get_expense_domain(all_tasks)
        expenses = self.env['hr.expense'].sudo().search(expenses_domain)
        purchase_lines = self._get_purchase_order_lines()
        moves = self._get_stock_moves().sorted('date', reverse=True)

        date_data = defaultdict(lambda: {'income': 0.0, 'cost': 0.0})

        inv_domain_line = (
            [('move_id.state', '=', 'posted'), ('sale_line_ids', 'in', sols.ids)]
            + self._get_date_domain('move_id.invoice_date')
        )
        for line in self.env['account.move.line'].search(inv_domain_line):
            if line.move_id.invoice_date:
                date_data[line.move_id.invoice_date]['income'] += self._convert_amount(
                    line.price_subtotal, line.currency_id, target_currency, line.move_id.invoice_date)

        for exp in expenses:
            if exp.date:
                date_data[exp.date]['cost'] += self._convert_amount(
                    exp.total_amount, exp.currency_id, target_currency, exp.date)

        for line in purchase_lines:
            d = line.date_order.date() if line.date_order else False
            if d:
                cost = line.product_qty * line.price_unit
                date_data[d]['cost'] += self._convert_amount(
                    cost, line.currency_id, target_currency, line.date_order)

        for move in moves:
            d = move.date.date() if move.date else False
            if d:
                qty = move.quantity if move.state == 'done' else move.product_uom_qty
                cost_native = (
                    move.price_unit or move.product_id.standard_price) * qty
                date_data[d]['cost'] += self._convert_amount(
                    cost_native, company_currency, target_currency, move.date)

        for al in timesheets:
            if al.date and self._check_date(al.date):
                date_data[al.date]['cost'] += self._convert_amount(
                    -al.amount, al.currency_id, target_currency, al.date)

        if not date_data:
            return Markup(
                '<div class="text-center p-5 text-muted">Sin datos para el rango seleccionado</div>')

        sorted_dates = sorted(date_data.keys())
        points = []
        cum_income = cum_cost = 0.0
        for d in sorted_dates:
            val = date_data[d]
            cum_income += val['income']
            cum_cost += val['cost']
            margin = cum_income - cum_cost
            points.append({
                'date_str': d.strftime('%d/%m'),
                'income': cum_income,
                'cost': cum_cost,
                'margin_pct': (margin / cum_income * 100.0) if cum_income else 0.0,
            })

        w, h, padding = 800, 380, 50
        max_val_chart = max(max(p['income'], p['cost'])
                            for p in points) * 1.1 or 1.0
        margins = [p['margin_pct'] for p in points]
        min_margin = min(min(margins), 0)
        max_margin = max(max(margins), 100)
        margin_range = max_margin - min_margin or 1.0

        def get_x(i):
            return padding + i * (w - 2 * padding) / (len(points) - 1 if len(points) > 1 else 1)

        def get_y(val):
            return h - padding - (val / max_val_chart) * (h - 2 * padding)

        def get_y_pct(pct):
            return h - padding - ((pct - min_margin) / margin_range) * (h - 2 * padding)

        pi_cmds, pc_cmds, pm_cmds = [], [], []
        income_pts = cost_pts = margin_pts = ''

        for i, p in enumerate(points):
            cx = get_x(i)
            cmd = "M" if i == 0 else "L"
            pi_cmds.append(f"{cmd} {cx:.1f},{get_y(p['income']):.1f}")
            pc_cmds.append(f"{cmd} {cx:.1f},{get_y(p['cost']):.1f}")
            pm_cmds.append(f"{cmd} {cx:.1f},{get_y_pct(p['margin_pct']):.1f}")

            income_pts += (
                f'<circle cx="{cx:.1f}" cy="{get_y(p["income"]):.1f}" r="4" '
                f'fill="#28a745" stroke="white" stroke-width="2">'
                f'<title>Ingresos {p["date_str"]}: {format_amount(self.env, p["income"], self.currency_id)}</title>'
                f'</circle>')
            cost_pts += (
                f'<circle cx="{cx:.1f}" cy="{get_y(p["cost"]):.1f}" r="4" '
                f'fill="#dc3545" stroke="white" stroke-width="2">'
                f'<title>Costos {p["date_str"]}: {format_amount(self.env, p["cost"], self.currency_id)}</title>'
                f'</circle>')
            margin_pts += (
                f'<circle cx="{cx:.1f}" cy="{get_y_pct(p["margin_pct"]):.1f}" r="4" '
                f'fill="#ffc107" stroke="white" stroke-width="2">'
                f'<title>Margen {p["date_str"]}: {p["margin_pct"]:.2f}%</title>'
                f'</circle>')

        pi_str = " ".join(pi_cmds)
        pc_str = " ".join(pc_cmds)
        pm_str = " ".join(pm_cmds)
        y_bot = h - padding
        pi_area = f"{pi_str} L {get_x(len(points)-1):.1f},{y_bot} L {get_x(0):.1f},{y_bot} Z"
        pc_area = f"{pc_str} L {get_x(len(points)-1):.1f},{y_bot} L {get_x(0):.1f},{y_bot} Z"

        y_ticks_svg = ''
        for i in range(5):
            pct = i / 4.0
            val = max_val_chart * pct
            yp = get_y(val)
            y_ticks_svg += (
                f'<line x1="{padding}" y1="{yp}" x2="{w-padding}" y2="{yp}" '
                f'stroke="#e9ecef" stroke-width="1" stroke-dasharray="4"/>'
                f'<text x="{padding-10}" y="{yp+4}" text-anchor="end" '
                f'font-size="10" fill="#6c757d" font-family="sans-serif">{int(val)}</text>')
            val_pct = min_margin + margin_range * pct
            yp_pct = get_y_pct(val_pct)
            y_ticks_svg += (
                f'<text x="{w-padding+10}" y="{yp_pct+4}" text-anchor="start" '
                f'font-size="10" fill="#ffc107" font-family="sans-serif">{int(val_pct)}%</text>')

        step = max(1, len(points) // 6) if len(points) > 12 else 1
        x_ticks_svg = ''.join(
            f'<text x="{get_x(i):.1f}" y="{h-padding+20}" text-anchor="middle" '
            f'font-size="10" fill="#6c757d" font-family="sans-serif">{points[i]["date_str"]}</text>'
            for i in range(0, len(points), step)
        )

        return Markup(f"""
        <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg"
             style="width:100%;height:auto;max-height:400px;font-family:-apple-system,system-ui,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
            <defs>
                <linearGradient id="gradIncome" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#28a745;stop-opacity:0.3"/>
                    <stop offset="100%" style="stop-color:#28a745;stop-opacity:0"/>
                </linearGradient>
                <linearGradient id="gradCost" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#dc3545;stop-opacity:0.3"/>
                    <stop offset="100%" style="stop-color:#dc3545;stop-opacity:0"/>
                </linearGradient>
                <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#000000" flood-opacity="0.1"/>
                </filter>
            </defs>
            {y_ticks_svg}
            <line x1="{padding}" y1="{h-padding}" x2="{w-padding}" y2="{h-padding}" stroke="#dee2e6" stroke-width="1"/>
            <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{h-padding}" stroke="#dee2e6" stroke-width="1"/>
            <path d="{pi_area}" fill="url(#gradIncome)"/>
            <path d="{pc_area}" fill="url(#gradCost)"/>
            <path d="{pi_str}" fill="none" stroke="#28a745" stroke-width="2.5" filter="url(#shadow)"/>
            <path d="{pc_str}" fill="none" stroke="#dc3545" stroke-width="2.5" filter="url(#shadow)"/>
            <path d="{pm_str}" fill="none" stroke="#ffc107" stroke-width="2.5" stroke-dasharray="5,5" filter="url(#shadow)"/>
            <g>{income_pts}{cost_pts}{margin_pts}</g>
            {x_ticks_svg}
            <g transform="translate({w-280},20)">
                <rect width="250" height="30" rx="5" fill="white" fill-opacity="0.8" stroke="#dee2e6"/>
                <circle cx="20" cy="15" r="4" fill="#28a745"/>
                <text x="30" y="19" font-size="11" fill="#333" font-weight="bold">Ingresos</text>
                <circle cx="90" cy="15" r="4" fill="#dc3545"/>
                <text x="100" y="19" font-size="11" fill="#333" font-weight="bold">Costos</text>
                <circle cx="150" cy="15" r="4" fill="#ffc107"/>
                <text x="160" y="19" font-size="11" fill="#333" font-weight="bold">Margen %</text>
            </g>
        </svg>""")

    # =========================================================================
    # SECCIÓN: COMPUTE STATS
    # =========================================================================

    # FIX 1 — @api.depends agregado. Sin este decorador Odoo no sabe cuándo
    # invalidar el caché de los campos compute de conteo (task_count, purchase_count,
    # expense_count, etc.), por lo que los KPIs no se actualizaban al guardar el wizard
    # o al cambiar filtros desde código (solo funcionaban en onchange de la UI).
    @api.depends(
        'project_ids', 'filter_type', 'task_ids', 'task_state_filter',
        'date_filter_type', 'date_from', 'date_to', 'include_archived',
        'ubicacion_ids', 'include_analytic_account',
    )
    def _compute_stats(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            all_tasks = tasks | tasks.mapped('child_ids')

            wizard.task_count = len(tasks)
            wizard.sale_order_count = len(wizard._get_sale_orders())
            wizard.purchase_count = len(wizard._get_purchase_orders())

            exp_domain = wizard._get_expense_domain(all_tasks)
            wizard.expense_count = self.env['hr.expense'].search_count(
                exp_domain)

            req_date_field = (
                'date_start'
                if 'date_start' in self.env['employee.purchase.requisition']._fields
                else 'create_date'
            )
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

            wizard.stock_move_count = len(wizard._get_stock_moves())

            timesheets = wizard._get_timesheets()
            wizard.timesheet_hours = sum(timesheets.mapped('unit_amount'))

            comp_lines = wizard._get_compensations()
            wizard.compensation_count = len(
                comp_lines.mapped('compensation_id'))

            wizard.invoice_count = len(wizard._get_related_invoices())

    # =========================================================================
    # SECCIÓN: ACCIONES DE VENTANA
    # =========================================================================

    def _get_project_task_domain(self, model_prefix=''):
        """
        Retorna dominio que incluye registros vinculados a tareas filtradas
        y registros del proyecto sin tarea (costos globales).

        FIX 3 — Cuando hay filtro de estado activo, se usa solo el dominio
        de tareas (all_tasks ya tiene el estado aplicado). Si se incluyera
        la rama project+task=False, registros globales del proyecto eludirían
        el filtro de estado.
        """
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')

        task_field = f'{model_prefix}task_id'
        project_field = f'{model_prefix}project_id'

        # FIX 3 — Solo usar la rama tarea cuando hay filtro de estado
        if self._has_task_state_filter():
            return [(task_field, 'in', all_tasks.ids)]

        if not self.task_ids and self.project_ids:
            return [
                '|',
                (task_field, 'in', all_tasks.ids),
                '&',
                (project_field, 'in', self.project_ids.ids),
                (task_field, '=', False),
            ]
        return [(task_field, 'in', all_tasks.ids)]

    def _get_action_view_base(self, name, res_model, domain):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_mode': 'tree,form',
            'domain': domain,
            'target': 'current',
        }

    def action_recalculate(self):
        self._compute_stats()
        self._compute_profitability()
        self._compute_content()
        return True

    def action_view_tasks(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        return self._get_action_view_base('Tareas Filtradas', 'project.task',
                                          [('id', 'in', tasks.ids)])

    def action_view_sale_orders(self):
        self.ensure_one()
        return self._get_action_view_base('Órdenes de Venta', 'sale.order',
                                          [('id', 'in', self._get_sale_orders().ids)])

    def action_view_purchase_orders(self):
        self.ensure_one()
        return self._get_action_view_base('Órdenes de Compra', 'purchase.order',
                                          [('id', 'in', self._get_purchase_orders().ids)])

    def action_view_timesheets(self):
        self.ensure_one()
        domain = self._get_project_task_domain() + self._get_date_domain('date')
        return self._get_action_view_base('Hojas de Horas', 'account.analytic.line', domain)

    def action_view_compensations(self):
        self.ensure_one()
        comp_domain = [('compensation_id.state', '=', 'applied')]

        if 'project_id' in self.env['compensation.line']._fields:
            comp_domain += self._get_project_task_domain()
        else:
            tasks = self._get_filtered_tasks()
            all_tasks = tasks | tasks.mapped('child_ids')
            comp_domain += [('task_id', 'in', all_tasks.ids)]

        date_field = 'date' if 'date' in self.env['compensation.line']._fields else 'create_date'
        comp_domain += self._get_date_domain(date_field)

        lines = self.env['compensation.line'].search(comp_domain)
        requests = lines.mapped('compensation_id')
        return self._get_action_view_base('Compensaciones', 'compensation.request',
                                          [('id', 'in', requests.ids)])

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

        req_date_field = (
            'date_start'
            if 'date_start' in self.env['employee.purchase.requisition']._fields
            else 'create_date'
        )

        if self.date_filter_type != 'none':
            if self.date_from:
                line_domain.append(
                    ('requisition_product_id.' + req_date_field, '>=', self.date_from))
            if self.date_to:
                line_domain.append(
                    ('requisition_product_id.' + req_date_field, '<=', self.date_to))

        lines = self.env['requisition.order'].search(line_domain)
        requisition_ids = lines.mapped('requisition_product_id').ids
        return self._get_action_view_base('Requisiciones', 'employee.purchase.requisition',
                                          [('id', 'in', requisition_ids)])

    def action_view_stock_moves(self):
        self.ensure_one()
        picking_ids = self._get_stock_moves().mapped('picking_id').ids
        return self._get_action_view_base('Movimientos de Almacén', 'stock.picking',
                                          [('id', 'in', picking_ids)])

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self._get_related_invoices()
        return {
            'name': 'Facturas de Cliente',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', invoices.ids)],
            'context': {'default_move_type': 'out_invoice'},
            'target': 'current',
        }

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref(
            'project_modificaciones.action_report_project_profitability_pdf'
        ).report_action(self)


# =============================================================================
# MODELO: Proveedor de datos para el reporte PDF QWeb
# =============================================================================

class ProjectProfitabilityReportPDF(models.AbstractModel):
    _name = 'report.project_modificaciones.report_project_profitability_pdf'
    _description = 'Proveedor de Datos — Reporte PDF Rentabilidad'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['project.profitability.report'].browse(docids)
        wizard = docs[0] if docs else self.env['project.profitability.report']

        profitability = {
            'expected_income':    wizard.expected_income,
            'invoiced_income':    wizard.invoiced_income,
            'to_invoice_income':  wizard.to_invoice_income,
            'total_expenses':     wizard.total_expenses,
            'expenses_billed':    wizard.expenses_billed,
            'expenses_to_bill':   wizard.expenses_to_bill,
            'total_purchases':    wizard.total_purchases,
            'purchases_billed':   wizard.purchases_billed,
            'purchases_to_bill':  wizard.purchases_to_bill,
            'purchase_incurred':  wizard.purchase_cost_incurred,
            'purchase_committed': wizard.purchase_committed,
            'total_stock_moves':  wizard.total_stock_moves,
            'stock_billed':       wizard.stock_billed,
            'stock_to_bill':      wizard.stock_to_bill,
            'timesheet_cost':     wizard.timesheet_cost,
            'timesheet_billed':   wizard.timesheet_billed,
            'timesheet_to_bill':  wizard.timesheet_to_bill,
            'margin_total':       wizard.margin_total,
            'profit_percentage':  wizard.profit_percentage,
            'total_costs': (
                wizard.total_expenses
                + wizard.total_purchases
                + wizard.total_stock_moves
                + wizard.timesheet_cost
            ),
        }

        kpi_counts = {
            'tasks':         wizard.task_count,
            'sale_orders':   wizard.sale_order_count,
            'purchases':     wizard.purchase_count,
            'expenses':      wizard.expense_count,
            'stock_moves':   wizard.stock_move_count,
            'invoices':      wizard.invoice_count,
            'compensations': wizard.compensation_count,
        }

        filter_ubicaciones = ', '.join(
            wizard.ubicacion_ids.mapped('name')) if wizard.ubicacion_ids else ''
        filter_projects = ', '.join(
            wizard.project_ids.mapped('name')) if wizard.project_ids else 'Todos'

        period_labels = {
            'none':       'Sin filtro de fecha',
            'today':      'Hoy',
            'this_month': 'Este mes',
            'this_year':  'Este año',
            'custom':     f"{wizard.date_from or '?'} → {wizard.date_to or '?'}",
        }
        filter_period = period_labels.get(wizard.date_filter_type, '—')

        state_labels = {
            'all':                  'Todas (excl. Canceladas)',
            '01_in_progress':       'En Proceso',
            '1_done':               'Hecho',
            '1_canceled':           'Cancelado',
            '04_waiting_normal':    'Esperando',
            '03_approved':          'Aprobado',
            '02_changes_requested': 'Cambios Solicitados',
        }
        filter_task_state = state_labels.get(wizard.task_state_filter, '')

        alerts = wizard._compute_alerts()

        tasks_obj = wizard._get_filtered_tasks()
        all_tasks = tasks_obj | tasks_obj.mapped('child_ids')

        def fmt(amount, _wizard=wizard):
            return format_amount(
                _wizard.env,
                float_round(float(amount or 0.0), precision_digits=2),
                _wizard.currency_id,
            )

        return {
            'doc_ids':   docids,
            'doc_model': 'project.profitability.report',
            'docs':      docs,
            'report_date':  fields.Date.context_today(wizard),
            'company_name': wizard.env.company.name,
            'currency_name': wizard.currency_id.name,
            'filter_ubicaciones': filter_ubicaciones,
            'filter_projects':    filter_projects,
            'filter_period':      filter_period,
            'filter_task_state':  filter_task_state,
            'profitability':   profitability,
            'kpi_counts':      kpi_counts,
            'timesheet_hours': wizard.timesheet_hours,
            'alert_negative_profit': alerts.get('alert_negative_profit', False),
            'alert_low_margin':      alerts.get('alert_low_margin', False),
            'purchases_list':   wizard._prepare_purchase_display_data(),
            'expenses_list':    wizard._prepare_expense_display_data(all_tasks),
            'stock_moves_list': wizard._prepare_stock_display_data(),
            'invoices_list':    wizard._prepare_invoice_display_data(),
            'fmt': fmt,
        }