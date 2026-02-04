from odoo import api, fields, models, _
from odoo.tools import format_amount
from odoo.tools.float_utils import float_round
import json


class ProjectProfitabilityReport(models.TransientModel):
    _name = 'project.profitability.report'
    _description = 'Reporte de Rentabilidad de Proyecto'
    _rec_name = 'project_id'

    project_id = fields.Many2one('project.project', string='Proyecto',
                                 required=True, domain="[('is_proyecto_obra', '=', True)]")

    # Filtros
    filter_type = fields.Selection([
        ('all', 'Todas las Tareas'),
        ('filter', 'Selección Manual')
    ], string='Filtrar por', default='all', required=True)

    task_ids = fields.Many2many('project.task', string='Tareas Específicas',
                                domain="[('project_id', '=', project_id)]")

    task_state_filter = fields.Selection([
        ('open', 'Abiertas (No canceladas/Hecho)'),
        ('done', 'Hecho'),
        ('all_active', 'Todas Activas')
    ], string="Estado de Tareas", default='open')

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

    @api.depends('project_id', 'filter_type', 'task_ids', 'task_state_filter')
    def _get_filtered_tasks(self):
        """Retorna el recordset de tareas basado en los filtros"""
        self.ensure_one()
        if not self.project_id:
            return self.env['project.task']

        domain = [('project_id', '=', self.project_id.id)]

        if self.filter_type == 'filter':
            if self.task_ids:
                return self.task_ids

        # Filtro por estado predefinido si es 'all' o no se seleccionaron tareas especificas
        if self.task_state_filter == 'open':
            domain.append(('state', 'not in', ['1_canceled', '1_done']))
        elif self.task_state_filter == 'done':
            domain.append(('state', '=', '1_done'))
        elif self.task_state_filter == 'all_active':
            domain.append(('state', '!=', '1_canceled'))

        return self.env['project.task'].search(domain)

    @api.depends('project_id', 'filter_type', 'task_ids', 'task_state_filter')
    def _compute_stats(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            # Incluir subtareas en el analisis de metricas
            all_tasks = tasks | tasks.mapped('child_ids')

            # Contamos tareas padre seleccionadas
            wizard.task_count = len(tasks)

            # Timesheets
            timesheets = self.env['account.analytic.line'].search([
                ('task_id', 'in', all_tasks.ids),
                ('project_id', '!=', False)
            ])
            wizard.timesheet_hours = sum(timesheets.mapped('unit_amount'))

            # Sale Orders (Unique)
            wizard.sale_order_count = len(all_tasks.mapped('sale_order_id'))

            # Purchase Orders
            po_lines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_tasks.ids),
                ('order_id.state', 'in', ('purchase', 'done')),
            ])
            wizard.purchase_count = len(po_lines.mapped('order_id'))

            # Expenses
            expenses = self.env['hr.expense'].search([
                ('task_id', 'in', all_tasks.ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ])
            wizard.expense_count = len(expenses)

            # Requisiciones
            requisitions = self.env['employee.purchase.requisition'].search([
                ('task_id', 'in', all_tasks.ids),
                # Asumiendo que queremos procesadas o en proceso
                ('state', 'not in', ['cancelled', 'new'])
            ])
            wizard.requisition_count = len(requisitions)

    @api.depends('project_id', 'filter_type', 'task_ids', 'task_state_filter')
    def _compute_profitability(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            all_task_ids = (tasks | tasks.mapped('child_ids')).ids
            all_tasks = self.env['project.task'].browse(all_task_ids)

            # --- INGRESOS ---
            sols = all_tasks.mapped('sale_line_id')
            expected = sum(sols.mapped('price_subtotal'))

            posted_lines = sols.mapped('invoice_lines').filtered(
                lambda l: l.move_id.state == 'posted')
            invoiced = sum(posted_lines.mapped('price_subtotal'))

            to_invoice = 0.0
            for sol in sols:
                qty_to_inv = sol.qty_delivered - sol.qty_invoiced
                to_invoice += qty_to_inv * sol.price_unit

            total_delivered_amount = sum(
                s.qty_delivered * s.price_unit for s in sols)

            wizard.expected_income = expected
            wizard.invoiced_income = invoiced
            wizard.to_invoice_income = to_invoice

            # --- COSTOS ---
            # 1. Gastos
            expenses = self.env['hr.expense'].search([
                ('task_id', 'in', all_task_ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ])
            wizard.total_expenses = sum(expenses.mapped('total_amount'))

            # 2. Compras
            purchase_lines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ('purchase', 'done'))
            ])
            wizard.total_purchases = sum(
                purchase_lines.mapped('price_subtotal'))

            # 3. Stock
            wizard.total_stock_moves = sum(
                all_tasks.mapped('stock_move_cost') or [0.0])

            # 4. Timesheets (Compensaciones)
            comp_lines = self.env['compensation.line'].search([
                ('task_id', 'in', all_task_ids),
                ('compensation_id.state', 'in', ['approve', 'applied'])
            ])
            wizard.timesheet_cost = sum(comp_lines.mapped('total_cost'))

            # TOTALES
            total_costs = wizard.total_expenses + wizard.total_purchases + \
                wizard.total_stock_moves + wizard.timesheet_cost

            wizard.margin_total = total_delivered_amount - total_costs

            if expected:
                wizard.profit_percentage = (
                    wizard.margin_total / expected) * 100.0
            else:
                wizard.profit_percentage = 0.0

    @api.depends('project_id', 'filter_type', 'task_ids', 'task_state_filter')
    def _compute_content(self):
        for wizard in self:
            tasks = wizard._get_filtered_tasks()
            all_task_ids = (tasks | tasks.mapped('child_ids')).ids

            # Reutilizamos lógica de stock moves lista
            stock_moves_list = []
            moves = self.env['stock.move'].search([
                ('task_id', 'in', all_task_ids),
                ('state', 'in', ['confirmed', 'assigned',
                 'partially_available', 'done'])
            ], order='date desc')  # Ordenar por fecha reciente

            # Optimización: Obtener nombres de productos y ubicaciones en lote si fuera necesario,
            # pero Odoo maneja cache.

            # --- LISTAS DETALLADAS PARA DRILL-DOWN ---
            # 1. Compras Detalladas
            purchases_list = []
            purchase_lines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ('purchase', 'done'))
            ], order='create_date desc')  # Fixed: date_order might not be sortable

            # Mapas de traducción
            purchase_state_map = {
                'draft': 'Borrador', 'sent': 'Enviado', 'to approve': 'Por Aprobar',
                'purchase': 'Pedido Compra', 'done': 'Bloqueado', 'cancel': 'Cancelado'
            }
            expense_state_map = {
                'draft': 'Borrador', 'reported': 'Enviado', 'approved': 'Aprobado',
                'post': 'Publicado', 'done': 'Pagado', 'refused': 'Rechazado'
            }

            for line in purchase_lines:
                purchases_list.append({
                    'order_name': line.order_id.name,
                    'order_id': line.order_id.id,
                    'date': line.date_order,
                    'partner': line.partner_id.name,
                    'product': line.product_id.display_name,
                    'qty': line.product_qty,
                    'price_unit': line.price_unit,
                    'total': line.price_subtotal,
                    'currency': line.currency_id.symbol,
                    'state': purchase_state_map.get(line.order_id.state, line.order_id.state),
                    'state_raw': line.order_id.state,  # Para colores
                })

            # 2. Gastos Detallados
            expenses_list = []
            expenses = self.env['hr.expense'].search([
                ('task_id', 'in', all_task_ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ], order='date desc')

            for exp in expenses:
                expenses_list.append({
                    'name': exp.name,
                    'employee': exp.employee_id.name,
                    'date': exp.date,
                    'product': exp.product_id.display_name,
                    'total': exp.total_amount,
                    'currency': exp.currency_id.symbol,
                    'state': expense_state_map.get(exp.state, exp.state),
                    'state_raw': exp.state,  # Para colores
                    'sheet_name': exp.sheet_id.name
                })

            for move in moves:
                price_unit = move.price_unit or move.product_id.standard_price
                qty_display = move.quantity if move.state == 'done' else move.product_uom_qty
                total_cost = qty_display * price_unit

                base_url = wizard.env['ir.config_parameter'].sudo(
                ).get_param('web.base.url')
                picking_url = f"{base_url}/web#id={move.picking_id.id}&model=stock.picking&view_type=form"

                state_map = {
                    'draft': 'Borrador', 'waiting': 'Esperando',
                    'confirmed': 'En espera', 'assigned': 'Reservado',
                    'done': 'Hecho', 'cancel': 'Cancelado',
                }

                stock_moves_list.append({
                    'product_name': move.product_id.display_name,
                    'task_name': move.task_id.name,  # Added: Ver de qué tarea viene
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

            # Valores para QWeb
            # Calcular porcentajes visuales similares al dashboard original
            # Simplificado para el ejemplo inicial, se puede detallar más como en dashboard_task
            total_facturado = 0
            total_expected = wizard.expected_income

            # --- DATOS PARA GRÁFICOS ---
            # Calculamos porcentajes del total de costos
            total_cost_base = wizard.total_expenses + wizard.total_purchases + \
                wizard.total_stock_moves + wizard.timesheet_cost or 1.0  # Evitar div/0

            p_stock = (wizard.total_stock_moves / total_cost_base) * 100
            p_purchases = (wizard.total_purchases / total_cost_base) * 100
            p_timesheets = (wizard.timesheet_cost / total_cost_base) * 100
            p_expenses = (wizard.total_expenses / total_cost_base) * 100

            # Construir gradiente CSS
            # Stock: Rojo (#dc3545), Compras: Azul (#0d6efd), Horas: Naranja (#fd7e14), Gastos: Morado (#6610f2)
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

            values = {
                'wizard': wizard,
                'stock_moves_list': stock_moves_list,
                'purchases_list': purchases_list,
                'expenses_list': expenses_list,
                'chart_data': chart_data,
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
        # Simplemente recarga la vista para forzar recomputo
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.profitability.report',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

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
