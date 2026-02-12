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

    # Filtros
    filter_type = fields.Selection([
        ('all', 'Todas las Tareas'),
        ('filter', 'Selección Manual')
    ], string='Tareas', default='all', required=True)

    task_ids = fields.Many2many('project.task', string='Tareas Específicas',
                                domain="[('project_id', 'in', project_ids)]")

    task_state_filter = fields.Selection([
        ('open', 'Abiertas (No canceladas/Hecho)'),
        ('done', 'Hecho'),
        ('all_active', 'Todas Activas')
    ], string="Estado de Tareas", default='open')

    include_archived = fields.Boolean(
        string='Tareas Archivadas', default=False,
        help="Si se marca, se incluirán las tareas archivadas en el análisis.")

    # Filtros de Fecha
    chart_type = fields.Selection([
        ('pie', 'Gráfico de Donut'),
        ('waterfall', 'Gráfico de Columnas'),
        ('line', 'Evolución Temporal')
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
                  'include_archived', 'chart_type', 'ubicacion_ids')
    def _onchange_filters(self):
        """
        Triggered when any filter changes in the UI. 
        We simply call the compute methods manually to update the values in the view
        before the user saves.
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
        """Retorna el recordset de tareas basado en los filtros"""
        self.ensure_one()
        if not self.project_ids:
            return self.env['project.task']

        domain = [('project_id', 'in', self.project_ids.ids)]

        # Filtro por Ubicacion
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

        # Filtro por estado predefinido active/done/etc
        if self.task_state_filter == 'open':
            domain.append(('state', 'not in', ['1_canceled', '1_done']))
        elif self.task_state_filter == 'done':
            domain.append(('state', '=', '1_done'))
        elif self.task_state_filter == 'all_active':
            domain.append(('state', '!=', '1_canceled'))

        return Task.search(domain)

    @api.depends('project_ids', 'filter_type', 'task_ids', 'task_state_filter', 'date_filter_type', 'date_from', 'date_to', 'include_archived')
    def _compute_stats(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            # Incluir subtareas en el analisis de metricas
            all_tasks = tasks | tasks.mapped('child_ids')

            # Contamos tareas padre seleccionadas
            wizard.task_count = len(tasks)

            # Timesheets
            timesheet_domain = [
                ('task_id', 'in', all_tasks.ids),
                ('project_id', '!=', False)
            ] + wizard._get_date_domain('date')

            # Optimización: Usamos read_group para sumar unit_amount directamente en DB
            # si solo necesitamos la suma de horas.
            timesheet_data = self.env['account.analytic.line'].read_group(
                timesheet_domain, ['unit_amount:sum'], [])
            wizard.timesheet_hours = timesheet_data[0]['unit_amount'] if timesheet_data else 0.0

            # Sale Orders
            # Apply date filter only if relevant, otherwise just count tasks related sales
            # For simplicity we apply filter to orders if generic date filter is active
            so_domain = [('id', 'in', all_tasks.mapped(
                'sale_order_id').ids)] + wizard._get_date_domain('date_order')
            wizard.sale_order_count = self.env['sale.order'].search_count(
                so_domain)

            # Purchase Orders
            # Optimización: Buscar directamente sobre purchase.order en lugar de purchase.order.line para evitar distinct en memoria
            po_domain = [
                ('order_line.task_id', 'in', all_tasks.ids),
                ('state', 'in', ('purchase', 'done')),
            ] + wizard._get_date_domain('date_order')
            wizard.purchase_count = self.env['purchase.order'].search_count(
                po_domain)

            # Expenses
            expense_domain = [
                ('task_id', 'in', all_tasks.ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ] + wizard._get_date_domain('date')

            wizard.expense_count = self.env['hr.expense'].search_count(
                expense_domain)

            # Requisiciones
            req_date_field = 'date_start' if 'date_start' in self.env[
                'employee.purchase.requisition']._fields else 'create_date'
            requisition_domain = [
                ('task_id', 'in', all_tasks.ids),
                ('state', 'not in', ['cancelled', 'new'])
            ] + wizard._get_date_domain(req_date_field)

            wizard.requisition_count = self.env['employee.purchase.requisition'].search_count(
                requisition_domain)

            # Stock Moves
            move_domain = [
                ('task_id', 'in', all_tasks.ids),
                ('state', 'in', ['confirmed', 'assigned',
                 'partially_available', 'done'])
            ] + wizard._get_date_domain('date')

            wizard.stock_move_count = self.env['stock.move'].search_count(
                move_domain)

    def _get_profitability_data(self, projects, date_from, date_to):
        """
        Calcula la rentabilidad para un set de proyectos en un rango de fechas.
        Retorna un diccionario con las métricas.
        """
        if not projects:
            return defaultdict(float)

        # Filtros de tareas (reutilizamos logica de filtro de tareas pero aplicada al set de proyectos)
        # Nota: self.task_ids y filtros de estado afectan qué tareas se consideran.
        # Si projects cambia, debemos asegurar que las tareas sean de esos proyectos.
        # Para simplificar y dado que el filtro de ubicación afecta a 'projects',
        # asumimos que 'projects' ya incluye el filtro de ubicación.
        # Sin embargo, 'self._get_filtered_tasks()' usa 'self.project_ids'.
        # Si estamos calculando para 'self.project_ids', usamos _get_filtered_tasks.

        # Lógica:
        # 1. Obtener tareas relevantes para estos proyectos, aplicando filtros de estado/archivo
        domain = [('project_id', 'in', projects.ids)]

        # Mismos filtros que en _get_filtered_tasks
        if self.include_archived:
            context = self.env.context.copy()
            context['active_test'] = False
            Task = self.env['project.task'].with_context(context)
        else:
            Task = self.env['project.task']

        if self.filter_type == 'filter':
            # Si hay selección manual, interceptamos solo las que pertenezcan a los proyectos dados
            if self.task_ids:
                domain.append(('id', 'in', self.task_ids.ids))

        if self.task_state_filter == 'open':
            domain.append(('state', 'not in', ['1_canceled', '1_done']))
        elif self.task_state_filter == 'done':
            domain.append(('state', '=', '1_done'))
        elif self.task_state_filter == 'all_active':
            domain.append(('state', '!=', '1_canceled'))

        tasks = Task.search(domain)
        all_task_ids = (tasks | tasks.mapped('child_ids')).ids
        all_tasks = self.env['project.task'].browse(all_task_ids)

        target_currency = self.currency_id
        company_currency = self.env.company.currency_id

        # Helper para conversion con fecha especifica
        def convert(amount, src_curr, date):
            return self._convert_amount(amount, src_curr, target_currency, date)

        # Helper para dominio de fechas dinamico
        def get_date_domain(field_name):
            d_dom = []
            if date_from:
                d_dom.append((field_name, '>=', date_from))
            if date_to:
                d_dom.append((field_name, '<=', date_to))
            return d_dom

        # --- INGRESOS ---
        sols = all_tasks.mapped('sale_line_id')
        expected = sum(convert(sol.price_subtotal, sol.currency_id, None)
                       for sol in sols)

        inv_domain = [('move_id.state', '=', 'posted')] + \
            get_date_domain('move_id.invoice_date')
        posted_lines = sols.mapped('invoice_lines').filtered_domain(inv_domain)
        invoiced = sum(convert(l.price_subtotal, l.currency_id,
                       l.move_id.invoice_date) for l in posted_lines)

        to_invoice = 0.0
        for sol in sols:
            qty_to_inv = sol.qty_delivered - sol.qty_invoiced
            amount = qty_to_inv * sol.price_unit
            to_invoice += convert(amount, sol.currency_id, None)

        # --- COSTOS ---
        # 1. Gastos
        expense_domain = [
            ('task_id', 'in', all_task_ids),
            ('sheet_id.state', 'in', ['approve', 'post', 'done'])
        ] + get_date_domain('date')
        expenses = self.env['hr.expense'].search(expense_domain)
        total_expenses = sum(convert(getattr(exp, 'total_amount', 0.0) or getattr(exp, 'total_amount_currency', 0.0) if hasattr(
            exp, 'total_amount_currency') else exp.unit_amount * exp.quantity, exp.currency_id, exp.date) for exp in expenses)
        # Nota: Ajuste por compatibilidad de campos en hr.expense según versión

        # 2. Compras
        purchase_domain = [
            ('task_id', 'in', all_task_ids),
            ('order_id.state', 'in', ('purchase', 'done'))
        ] + get_date_domain('date_order')
        purchase_lines = self.env['purchase.order.line'].search(
            purchase_domain)

        p_incurred = 0.0
        p_committed = 0.0
        for pl in purchase_lines:
            qty_done = max(pl.qty_invoiced, pl.qty_received)
            qty_ordered = pl.product_qty
            price = pl.price_unit

            p_incurred += convert(qty_done * price,
                                  pl.currency_id, pl.date_order)

            qty_rem = qty_ordered - qty_done
            if qty_rem > 0:
                p_committed += convert(qty_rem * price,
                                       pl.currency_id, pl.date_order)

        total_purchases = p_incurred + p_committed

        # 3. Stock
        stock_domain = [
            ('task_id', 'in', all_task_ids),
            ('state', 'in', ['confirmed', 'assigned',
             'partially_available', 'done'])
        ] + get_date_domain('date')
        stock_moves = self.env['stock.move'].search(stock_domain)

        stock_cost = 0.0
        for move in stock_moves:
            idx_cost = move.product_id.standard_price
            qty = move.quantity if move.state == 'done' else move.product_uom_qty
            stock_cost += convert(idx_cost * qty, company_currency, move.date)

        # 4. Timesheets
        comp_domain = [
            ('task_id', 'in', all_task_ids),
            ('compensation_id.state', 'in', ['approve', 'applied'])
        ]
        comp_lines = self.env['compensation.line'].search(comp_domain)
        ts_cost = 0.0

        for comp in comp_lines:
            # Filtro fecha manual en memoria pues compensation.line puede no tener index o campo directo simple
            c_date = comp.create_date.date() if comp.create_date else False
            if c_date:
                if date_from and c_date < date_from:
                    continue
                if date_to and c_date > date_to:
                    continue

            ts_cost += convert(comp.total_cost,
                               company_currency, comp.create_date)

        # TOTALES
        total_costs_real = total_expenses + total_purchases + stock_cost + ts_cost
        margin_total = invoiced - total_costs_real

        profit_pct = 0.0
        if invoiced:
            profit_pct = (margin_total / invoiced) * 100.0
        elif expected:
            profit_pct = (margin_total / expected) * 100.0

        return {
            'expected_income': expected,
            'invoiced_income': invoiced,
            'to_invoice_income': to_invoice,
            'total_expenses': total_expenses,
            'total_purchases': total_purchases,
            'purchase_incurred': p_incurred,
            'purchase_committed': p_committed,
            'total_stock_moves': stock_cost,
            'timesheet_cost': ts_cost,
            'margin_total': margin_total,
            'profit_percentage': profit_pct,
            'total_costs': total_costs_real
        }

    @api.depends('project_ids', 'filter_type', 'task_ids', 'task_state_filter',
                 'date_filter_type', 'date_from', 'date_to', 'include_archived',
                 'ubicacion_ids')
    def _compute_profitability(self):
        for wizard in self:
            # 1. Periodo Actual
            # Filtramos proyectos por ubicacion primero
            projects = wizard.project_ids
            if wizard.ubicacion_ids:
                projects = projects.filtered(
                    lambda p: p.ubicacion in wizard.ubicacion_ids)

            data = wizard._get_profitability_data(
                projects, wizard.date_from, wizard.date_to)

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
            all_task_ids = (tasks | tasks.mapped('child_ids')).ids
            company_currency = wizard.env.company.currency_id
            target_currency = wizard.currency_id

            # Stock Moves List
            stock_domain = [
                ('task_id', 'in', all_task_ids),
                ('state', 'in', ['confirmed', 'assigned',
                 'partially_available', 'done'])
            ] + wizard._get_date_domain('date')
            moves = self.env['stock.move'].search(
                stock_domain, order='date desc')

            stock_moves_list = []
            state_map = {
                'draft': 'Borrador', 'waiting': 'Esperando',
                'confirmed': 'En espera', 'assigned': 'Reservado',
                'done': 'Hecho', 'cancel': 'Cancelado',
            }

            base_url = wizard.env['ir.config_parameter'].sudo(
            ).get_param('web.base.url')

            for move in moves:
                price_unit = move.price_unit or move.product_id.standard_price
                qty_display = move.quantity if move.state == 'done' else move.product_uom_qty
                total_cost = qty_display * price_unit
                picking_url = f"{base_url}/web#id={move.picking_id.id}&model=stock.picking&view_type=form"

                stock_moves_list.append({
                    'product_name': move.product_id.display_name,
                    'task_name': move.task_id.name,
                    'project_name': move.task_id.project_id.name,
                    'date': move.date,
                    'quantity': qty_display,
                    'uom': move.product_uom.name,
                    'reference': move.reference,
                    'picking': move.picking_id.name,
                    'picking_url': picking_url,
                    'price_unit': price_unit,
                    'total_cost': total_cost,
                    'state_label': state_map.get(move.state, move.state),
                    'state_raw': move.state,
                    'location_id': move.location_id.display_name,
                    'location_dest_id': move.location_dest_id.display_name,
                    'lot_name': ", ".join(move.move_line_ids.mapped('lot_id.name')) or "-"
                })

            # Compras Detalladas
            purchases_list = []
            po_domain = [
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ('purchase', 'done'))
            ] + wizard._get_date_domain('date_order')
            purchase_lines = self.env['purchase.order.line'].search(
                po_domain, order='create_date desc')

            purchase_state_map = {
                'draft': 'Borrador', 'sent': 'Enviado', 'to approve': 'Por Aprobar',
                'purchase': 'Pedido Compra', 'done': 'Bloqueado', 'cancel': 'Cancelado'
            }

            for line in purchase_lines:
                purchases_list.append({
                    'order_name': line.order_id.name,
                    'order_id': line.order_id.id,
                    'project_name': line.task_id.project_id.name,
                    'task_name': line.task_id.name,
                    'purchase_order_model': 'purchase.order',  # For linking
                    'date': line.date_order,
                    'partner': line.partner_id.name,
                    'product': line.product_id.display_name,
                    'qty': line.product_qty,
                    'price_unit': line.price_unit,
                    'total': line.price_subtotal,
                    'currency': line.currency_id.symbol,
                    'state': purchase_state_map.get(line.order_id.state, line.order_id.state),
                    'state_raw': line.order_id.state,
                })

            # Gastos Detallados
            expenses_list = []
            exp_domain = [
                ('task_id', 'in', all_task_ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ] + wizard._get_date_domain('date')
            expenses = self.env['hr.expense'].search(
                exp_domain, order='date desc')

            expense_state_map = {
                'draft': 'Borrador', 'reported': 'Enviado', 'approved': 'Aprobado',
                'post': 'Publicado', 'done': 'Pagado', 'refused': 'Rechazado'
            }

            for exp in expenses:
                # URL
                exp_url = f"/web#id={exp.id}&model=hr.expense&view_type=form"

                expenses_list.append({
                    'name': exp.name,
                    'employee': exp.employee_id.name,
                    'project_name': exp.task_id.project_id.name,
                    'task_name': exp.task_id.name,
                    'date': exp.date,
                    'product': exp.product_id.display_name,
                    'total': exp.total_amount,
                    'currency': exp.currency_id.symbol,
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

            # --- COLUMN CHART DATA CALCULATION (TRUE WATERFALL) ---
            column_data = []
            if wizard.chart_type == 'waterfall':
                if not wizard.currency_id:
                    currency = company_currency
                else:
                    currency = wizard.currency_id

                rev = wizard.invoiced_income
                # Costs (Negative for waterfall steps)
                exp = -wizard.total_expenses
                # Simplified Purchases
                pur_total = -wizard.total_purchases
                stk = -wizard.total_stock_moves
                tsh = -wizard.timesheet_cost

                final_margin = rev + exp + pur_total + stk + tsh

                # Structure: (Label, Value, Type, Color)
                # Type: 'start', 'step', 'end' ?
                # We need start/end levels.

                # Steps:
                # 1. Ingresos (Base) -> Start at 0, Height = Rev
                # 2. Gastos -> Start at Rev, Height = -Exp (Down)
                # 3. Compras Incur. -> Start at (Rev+Exp), Height = -PurInc
                # 4. Compras Compr. -> ...
                # ...
                # Last: Margen -> Start at 0, Height = Margin (or residue)

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

                    # Determine bar geometric properties (percentage of container height)
                    # We assume 0 is at bottom (0%). Max is Top (100%).
                    # If values are negative? Waterfall works best with positive revenue > costs.
                    # We map [0, max_val] to [0, 100%].

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

            # Timesheets (Compensations)
            comp_domain = [
                ('task_id', 'in', all_task_ids),
                ('compensation_id.state', 'in', ['approve', 'applied'])
            ]
            comp_lines = self.env['compensation.line'].search(comp_domain)

            # Timesheets List
            timesheets_list = []

            # Obtener traducciones de estados si es posible
            ts_state_map = {}
            if comp_lines:
                try:
                    # Intento de obtener el modelo de compensation_id (asumiendo compensation.request)
                    # Si falla, usaremos el valor raw
                    sample_comp = comp_lines[0].compensation_id
                    if sample_comp:
                        ts_state_map = dict(
                            sample_comp._fields['state'].selection)
                except Exception:
                    pass

            for comp in comp_lines:
                # Filtrar fecha si aplica
                if wizard.date_filter_type == 'none' or wizard._check_date(comp.create_date):
                    # URL
                    ts_url = f"/web#id={comp.id}&model=compensation.line&view_type=form"

                    timesheets_list.append({
                        'employee': comp.employee_id.name,
                        'project_name': comp.task_id.project_id.name,
                        'date': comp.create_date,
                        'description': comp.justification or comp.task_id.name,
                        'task': comp.task_id.name,
                        'total': comp.total_cost,
                        # Asumimos moneda compañia para compensaciones
                        'currency': company_currency.symbol,
                        'total': comp.total_cost,
                        # Asumimos moneda compañia para compensaciones
                        'currency': company_currency.symbol,
                        'state_label': ts_state_map.get(comp.compensation_id.state, comp.compensation_id.state),
                        'state_raw': comp.compensation_id.state,
                        'ts_url': ts_url
                    })

            # --- LINE CHART DATA GENERATION ---
            line_chart_svg = ""
            if wizard.chart_type == 'line':
                # 1. Aggregate Data by Date
                date_data = defaultdict(lambda: {'income': 0.0, 'cost': 0.0})

                # Incomes (Invoices)
                # Re-fetch posted lines to ensure we have dates accessible
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
                for comp in comp_lines:
                    d = comp.create_date.date() if comp.create_date else False
                    if d and wizard._check_date(d):
                        date_data[d]['cost'] += wizard._convert_amount(
                            comp.total_cost, company_currency, target_currency, comp.create_date)

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

            # 1. Negative Profit (Cost > Income)
            if wizard.margin_total < 0:
                alert_negative_profit = True

            # 2. Low Margin (Positive but < 10%)
            # We assume profit_percentage is 0-100 base
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
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        orders = all_tasks.mapped('sale_order_id')
        return self._get_action_view_base('Órdenes de Venta', 'sale.order', [('id', 'in', orders.ids)])

    def action_view_purchase_orders(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        lines = self.env['purchase.order.line'].search([
            ('task_id', 'in', all_tasks.ids),
            ('order_id.state', 'in', ('purchase', 'done'))
        ])
        orders = lines.mapped('order_id')
        return self._get_action_view_base('Órdenes de Compra', 'purchase.order', [('id', 'in', orders.ids)])

    def action_view_timesheets(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        return self._get_action_view_base('Hojas de Horas', 'account.analytic.line', [('task_id', 'in', all_tasks.ids)])

    def action_view_expenses(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        return self._get_action_view_base('Gastos', 'hr.expense', [
            ('task_id', 'in', all_tasks.ids),
            ('sheet_id.state', 'in', ['approve', 'post', 'done'])
        ])

    def action_view_requisitions(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        return self._get_action_view_base('Requisiciones', 'employee.purchase.requisition', [
            ('task_id', 'in', all_tasks.ids),
            ('state', 'not in', ['cancelled', 'new'])
        ])

    def action_view_stock_moves(self):
        self.ensure_one()
        tasks = self._get_filtered_tasks()
        all_tasks = tasks | tasks.mapped('child_ids')
        moves = self.env['stock.move'].search([
            ('task_id', 'in', all_tasks.ids),
            ('state', 'in', ['confirmed', 'assigned',
             'partially_available', 'done'])
        ])
        picking_ids = moves.mapped('picking_id').ids
        return self._get_action_view_base('Movimientos de Almacén', 'stock.picking', [('id', 'in', picking_ids)])
