from odoo import api, fields, models, _
from odoo.tools import format_amount
from odoo.tools.float_utils import float_round


class AnalyticsTaskDashboard(models.TransientModel):
    _name = 'task.update'
    _description = 'Dashboard de Tarea'
    _rec_name = 'name'

    # --- Campos (Sin cambios) ---
    task_id = fields.Many2one('project.task', string='Tarea', required=True)
    name = fields.Char(string='Nombre', compute='_compute_name')
    content = fields.Html(string='Contenido',
                          compute='_compute_content', sanitize=False)
    user_id = fields.Many2one(
        'res.users', string='Autor', default=lambda self: self.env.user)
    date = fields.Date(default=fields.Date.context_today)
    status_text = fields.Char(string='Estado', compute='_compute_status_text')

    # Métricas KPIs
    timesheet_count = fields.Integer(
        string='Hojas de horas', compute='_compute_stats')
    timesheet_hours = fields.Float(
        string='Horas', compute='_compute_stats', digits=(16, 2))
    subtask_count = fields.Integer(string='Tareas', compute='_compute_stats')
    sale_order_count = fields.Integer(
        string='Órdenes de venta', compute='_compute_stats')
    sale_line_count = fields.Integer(
        string='Artículos OV', compute='_compute_stats')
    purchase_count = fields.Integer(
        string='Órdenes de compra', compute='_compute_stats')
    expense_count = fields.Integer(string='Gastos', compute='_compute_stats')
    avances_count = fields.Integer(string='Avances', compute='_compute_stats')
    stock_move_count = fields.Integer(
        string='Mov. Almacén', compute='_compute_stats')
    requisition_count = fields.Integer(
        string='Requisiciones', compute='_compute_stats')

    # Rentabilidad
    expected_income = fields.Monetary(
        string='Ingresos esperados', compute='_compute_profitability', currency_field='currency_id')
    invoiced_income = fields.Monetary(
        string='Facturado', compute='_compute_profitability', currency_field='currency_id')
    to_invoice_income = fields.Monetary(
        string='Por facturar', compute='_compute_profitability', currency_field='currency_id')
    total_expenses = fields.Monetary(
        string='Total Gastos', compute='_compute_profitability', currency_field='currency_id')
    total_purchases = fields.Monetary(
        string='Total Compras', compute='_compute_profitability', currency_field='currency_id')
    total_stock_moves = fields.Monetary(
        string='Total Mov. Almacén', compute='_compute_profitability', currency_field='currency_id')
    total_costs = fields.Monetary(
        string='Total Costos', compute='_compute_profitability', currency_field='currency_id')
    costs_total = fields.Monetary(
        string='Costos', compute='_compute_profitability', currency_field='currency_id')
    margin_total = fields.Monetary(
        string='Margen', compute='_compute_profitability', currency_field='currency_id')
    total_facturado = fields.Monetary(
        string='Costos Facturados Prov.', compute='_compute_profitability', currency_field='currency_id')
    total_a_facturar = fields.Monetary(
        string='Costos Por Facturar Prov.', compute='_compute_profitability', currency_field='currency_id')
    profit_percentage = fields.Float(
        string='% Rentabilidad', compute='_compute_profitability')
    expected_percentage = fields.Float(string='% esperado')
    facturado_margen = fields.Float(
        string='% Margen Fact', compute='_compute_profitability')
    to_bill_to_invoice_percentage = fields.Float(string='% por facturar')
    billed_invoiced_percentage = fields.Float(string='% facturado')
    total_expected = fields.Monetary(
        string='Total esperado', compute='_compute_profitability', currency_field='currency_id')
    total_to_bill_to_invoice = fields.Monetary(
        string='Total por facturar', compute='_compute_profitability', currency_field='currency_id')
    total_billed_invoiced = fields.Monetary(
        string='Total facturado', compute='_compute_profitability', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    total_entregado = fields.Monetary(
        string='Total entregado', compute='_compute_profitability', currency_field='currency_id')
    esperado_sin_orden = fields.Monetary(
        string='Esperado S/OV', compute='_compute_profitability')

    # --- Función Auxiliar (CORREGIDA INDENTACIÓN) ---
    def _get_all_task_ids(self):
        """Retorna una lista con el ID de la tarea actual y sus subtareas"""
        self.ensure_one()
        return [self.task_id.id] + self.task_id.child_ids.ids

    def _compute_status_text(self):
        for wizard in self:
            wizard.status_text = wizard.task_id.stage_id.display_name if wizard.task_id and wizard.task_id.stage_id else ''

    def _compute_name(self):
        for wizard in self:
            task_name = wizard.task_id.display_name if wizard.task_id else ''
            wizard.name = f"Tablero de {task_name}" if task_name else 'Tablero'

    @api.depends('task_id')
    def _compute_content(self):
        for wizard in self:
            # OPTIMIZACIÓN: Usamos la función auxiliar aquí también
            all_task_ids = wizard._get_all_task_ids()

            expenses = self.env['hr.expense'].search([
                ('task_id', 'in', all_task_ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ])

            polines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ('purchase', 'done')),
            ])

            total_expenses = sum(expenses.mapped(
                'total_amount')) if expenses else 0.0
            total_purchases = sum(polines.mapped(
                'price_subtotal')) if polines else 0.0

            vendor_bill_lines = self.env['account.move.line'].search([
                ('purchase_line_id.task_id', 'in', all_task_ids),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ])
            purchases_billed = sum(vendor_bill_lines.mapped(
                'price_subtotal')) if vendor_bill_lines else 0.0
            purchases_to_bill = max(total_purchases - purchases_billed, 0.0)

            expenses_billed = 0.0
            expenses_to_bill = 0.0
            if expenses:
                expenses_billed = sum(expenses.filtered(
                    lambda e: e.sheet_id and e.sheet_id.state in ('post', 'done')).mapped('total_amount'))
                expenses_to_bill = max(total_expenses - expenses_billed, 0.0)

            # --- Timesheets Logic ---
            comp_lines = self.env['compensation.line'].search([
                ('task_id', 'in', all_task_ids),
                ('compensation_id.state', 'in', ['approved', 'applied'])
            ])
            timesheet_cost = sum(comp_lines.mapped('total_cost'))
            timesheet_billed = sum(comp_lines.filtered(
                lambda l: l.compensation_id.state == 'applied').mapped('total_cost'))
            timesheet_to_bill = max(timesheet_cost - timesheet_billed, 0.0)

            # --- Stock Moves Logic ---
            # CORREGIDO: Suma de stock de padre + hijos
            tasks_for_stock = self.env['project.task'].browse(all_task_ids)
            stock_billed = sum(tasks_for_stock.mapped(
                'stock_move_cost') or [0.0])

            all_moves = self.env['stock.move'].search([
                ('task_id', 'in', all_task_ids),
                ('state', 'in', ['confirmed', 'assigned',
                 'partially_available', 'done']),
                # ('picking_type_id.code', '=', 'outgoing')
            ])
            scope_qty_per_product = {}
            for move in all_moves:
                scope_qty_per_product[move.product_id.id] = scope_qty_per_product.get(
                    move.product_id.id, 0.0) + move.product_uom_qty

            purchased_qty_per_product = {}
            purchase_lines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ['purchase', 'done'])
            ])
            for line in purchase_lines:
                purchased_qty_per_product[line.product_id.id] = purchased_qty_per_product.get(
                    line.product_id.id, 0.0) + line.product_qty

            stock_expected = 0.0
            for product_id, scope_qty in scope_qty_per_product.items():
                purchased_qty = purchased_qty_per_product.get(product_id, 0.0)
                chargeable_qty = max(0.0, scope_qty - purchased_qty)
                if chargeable_qty > 0:
                    product = self.env['product.product'].browse(product_id)
                    stock_expected += chargeable_qty * product.standard_price

            stock_to_bill = max(stock_expected - stock_billed, 0.0)

            total_facturado = expenses_billed + \
                purchases_billed + timesheet_billed + stock_billed
            total_a_facturar = expenses_to_bill + \
                purchases_to_bill + timesheet_to_bill + stock_to_bill

            wizard.total_facturado = total_facturado
            wizard.total_a_facturar = total_a_facturar

            esperado_sin_orden = 0.0
            for avance in wizard.task_id.sub_update_ids:
                if avance.precio_unidad and avance.unit_progress:
                    esperado_sin_orden += avance.precio_unidad * avance.unit_progress

            # Lista de movimientos para tabla HTML
            stock_moves_list = []
            moves = self.env['stock.move'].search([
                ('task_id', 'in', all_task_ids),
                ('state', 'in', ['confirmed', 'assigned',
                 'partially_available', 'done']),
                # ('picking_type_id.code', '=', 'outgoing')
            ])

            for move in moves:
                price_unit = move.price_unit or move.product_id.standard_price
                qty_display = move.quantity if move.state == 'done' else move.product_uom_qty
                total_cost = qty_display * price_unit
                base_url = wizard.env['ir.config_parameter'].sudo(
                ).get_param('web.base.url')
                picking_url = f"{base_url}/web#id={move.picking_id.id}&model=stock.picking&view_type=form"
                lot_names = ", ".join(
                    move.move_line_ids.mapped('lot_id.name')) or "-"

                state_map = {
                    'draft': 'Borrador', 'waiting': 'Esperando otra operación',
                    'confirmed': 'En espera', 'assigned': 'Reservado',
                    'done': 'Hecho', 'cancel': 'Cancelado',
                }
                state_label = state_map.get(move.state, move.state)
                req_name = move.picking_id.requisition_id2.name or "-"

                stock_moves_list.append({
                    'product_name': move.product_id.display_name,
                    'date': move.date,
                    'quantity': qty_display,
                    'uom': move.product_uom.name,
                    'reference': move.reference,
                    'picking': move.picking_id.name,
                    'picking_id': move.picking_id.id,
                    'picking_url': picking_url,
                    'price_unit': price_unit,
                    'total_cost': total_cost,
                    'state_label': state_label,
                    'state_raw': move.state,
                    'location_id': move.location_id.display_name,
                    'location_dest_id': move.location_dest_id.display_name,
                    'lot_name': lot_names,
                    'requisition': req_name,
                })

            values = {
                'wizard_id': wizard.id,
                'profitability': {
                    'expected_income': wizard.expected_income,
                    'timesheet_cost': timesheet_cost,
                    'timesheet_billed': timesheet_billed,
                    'timesheet_to_bill': timesheet_to_bill,
                    'to_invoice_income': wizard.to_invoice_income,
                    'invoiced_income': wizard.invoiced_income,
                    'total_expenses': total_expenses,
                    'expenses_to_bill': expenses_to_bill,
                    'expenses_billed': expenses_billed,
                    'total_facturado': total_facturado,
                    'total_a_facturar': total_a_facturar,
                    'total_purchases': total_purchases,
                    'purchases_to_bill': purchases_to_bill,
                    'purchases_billed': purchases_billed,
                    'total_stock_moves': stock_expected,
                    'stock_billed': stock_billed,
                    'stock_to_bill': stock_to_bill,
                    'esperado_sin_orden': esperado_sin_orden,
                    'margen_total': wizard.margin_total,
                    'expected_percentage': wizard.expected_percentage,
                    'total_billed_invoiced': wizard.total_billed_invoiced,
                    'total_to_bill_to_invoice': wizard.total_to_bill_to_invoice,
                    'total_expected': wizard.total_expected,
                    'facturado_margen': wizard.facturado_margen,
                    'billed_invoiced_percentage': wizard.billed_invoiced_percentage,
                    'profit_percentage': wizard.profit_percentage,
                    'to_bill_to_invoice_percentage': wizard.to_bill_to_invoice_percentage,
                    'total_entregado': wizard.total_entregado,
                    'total_costs': wizard.total_costs
                },
                'stock_moves_list': stock_moves_list,
                'format_monetary': lambda v: format_amount(self.env, float_round(v, precision_digits=3), wizard.currency_id),
                'format_percentage': lambda v: f"{v:.2f}%" if v is not False else '0.00%',
                'format_signed_percentage': lambda v: f"{('+' if v >= 0 else '')}{v:.2f}%" if v is not False else '0.00%',
            }
            wizard.content = self.env['ir.qweb']._render(
                'project_modificaciones.task_dashboard_template', values)

    @api.depends('task_id')
    def _compute_stats(self):
        for wizard in self:
            # OPTIMIZACIÓN: Usamos la función auxiliar
            all_task_ids = wizard._get_all_task_ids()

            timesheets = self.env['account.analytic.line'].search([
                ('task_id', 'in', all_task_ids),
                ('project_id', '!=', False)
            ])
            wizard.timesheet_count = len(timesheets)
            wizard.timesheet_hours = sum(timesheets.mapped('unit_amount'))

            wizard.subtask_count = len(wizard.task_id.child_ids)

            tasks = self.env['project.task'].browse(all_task_ids)
            wizard.sale_order_count = len(tasks.mapped('sale_order_id'))
            wizard.sale_line_count = len(tasks.mapped('sale_line_id'))


#            wizard.purchase_count = self.env['purchase.order.line'].search_count([
#                ('task_id', 'in', all_task_ids),
#                ('order_id.state', 'in', ('purchase', 'done')),
#            ])
            po_lines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ('purchase', 'done')),
            ])
            # Usamos mapped para obtener las órdenes únicas (evita duplicados si hay varias líneas)
            wizard.purchase_count = len(po_lines.mapped('order_id'))

            wizard.expense_count = self.env['hr.expense'].search_count([
                ('task_id', 'in', all_task_ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ])

            wizard.stock_move_count = self.env['stock.move'].search_count([
                ('task_id', 'in', all_task_ids)
            ])

            wizard.requisition_count = self.env['employee.purchase.requisition'].search_count([
                ('task_id', 'in', all_task_ids)
            ])

            wizard.avances_count = 0

    @api.depends('task_id')
    def _compute_profitability(self):
        for wizard in self:
            # OPTIMIZACIÓN: Usamos la función auxiliar
            all_task_ids = wizard._get_all_task_ids()

            all_tasks = self.env['project.task'].browse(all_task_ids)

            sols = all_tasks.mapped('sale_line_id')
            expected = sum(sols.mapped('price_subtotal'))

            posted_lines = sols.mapped('invoice_lines').filtered(
                lambda l: l.move_id.state == 'posted')
            invoiced = sum(posted_lines.mapped('price_subtotal'))

            total_delivered_amount = sum(
                s.qty_delivered * s.price_unit for s in sols)

            to_invoice = 0.0
            for sol in sols:
                qty_to_inv = sol.qty_delivered - sol.qty_invoiced
                to_invoice += qty_to_inv * sol.price_unit

            wizard.expected_income = expected
            wizard.invoiced_income = invoiced
            wizard.to_invoice_income = to_invoice
            wizard.total_entregado = total_delivered_amount

            # --- Costos ---
            expenses = self.env['hr.expense'].search([
                ('task_id', 'in', all_task_ids),
                ('sheet_id.state', 'in', ['approve', 'post', 'done'])
            ])
            expenses_total = sum(expenses.mapped('total_amount'))

            expenses_billed = sum(expenses.filtered(
                lambda e: e.sheet_id.state in ('post', 'done')).mapped('total_amount'))
            expenses_to_bill = max(expenses_total - expenses_billed, 0.0)

            purchase_lines = self.env['purchase.order.line'].search([
                ('task_id', 'in', all_task_ids),
                ('order_id.state', 'in', ('purchase', 'done'))
            ])
            purchases_total = sum(purchase_lines.mapped('price_subtotal'))

            vendor_bill_lines = self.env['account.move.line'].search([
                ('purchase_line_id.task_id', 'in', all_task_ids),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ])
            purchases_billed = sum(vendor_bill_lines.mapped('price_subtotal'))
            purchases_to_bill = max(purchases_total - purchases_billed, 0.0)

            stock_cost = sum(all_tasks.mapped('stock_move_cost') or [0.0])
            stock_billed = stock_cost
            stock_to_bill = 0.0

            comp_lines = self.env['compensation.line'].search([
                ('task_id', 'in', all_task_ids),
                ('compensation_id.state', 'in', ['approve', 'applied'])
            ])
            timesheet_cost = sum(comp_lines.mapped('total_cost'))
            timesheet_billed = sum(comp_lines.filtered(
                lambda l: l.compensation_id.state == 'applied').mapped('total_cost'))
            timesheet_to_bill = max(timesheet_cost - timesheet_billed, 0.0)

            wizard.total_expenses = expenses_total
            wizard.total_purchases = purchases_total
            wizard.total_stock_moves = stock_cost
            wizard.total_costs = expenses_total + \
                purchases_total + stock_cost + timesheet_cost
            wizard.costs_total = wizard.total_costs

            total_facturado_prov = expenses_billed + \
                purchases_billed + timesheet_billed + stock_billed
            total_a_facturar_prov = expenses_to_bill + \
                purchases_to_bill + timesheet_to_bill + stock_to_bill

            wizard.total_facturado = total_facturado_prov
            wizard.total_a_facturar = total_a_facturar_prov

            wizard.margin_total = wizard.total_entregado - wizard.total_costs
            wizard.total_expected = wizard.total_entregado - wizard.costs_total
            wizard.total_billed_invoiced = wizard.invoiced_income - total_facturado_prov
            wizard.total_to_bill_to_invoice = wizard.to_invoice_income - total_a_facturar_prov

            wizard.profit_percentage = (
                wizard.margin_total / expected * 100.0) if expected else 0.0
            wizard.expected_percentage = (
                wizard.margin_total / wizard.total_entregado * 100.0) if wizard.total_entregado else 0.0
            wizard.facturado_margen = (
                wizard.total_billed_invoiced / wizard.invoiced_income * 100.0) if wizard.invoiced_income else 0.0

            if wizard.to_invoice_income:
                percent = (wizard.total_to_bill_to_invoice /
                           wizard.to_invoice_income * 100.0)
                wizard.to_bill_to_invoice_percentage = percent
                wizard.billed_invoiced_percentage = percent
            else:
                wizard.to_bill_to_invoice_percentage = 0.0
                wizard.billed_invoiced_percentage = 0.0

            esperado_sin_ov = 0.0
            for t in all_tasks:
                for avance in t.sub_update_ids:
                    if avance.precio_unidad and avance.unit_progress:
                        esperado_sin_ov += avance.precio_unidad * avance.unit_progress
            wizard.esperado_sin_orden = esperado_sin_ov

    # Acciones de navegación
    def action_view_subtasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subtareas',
            'res_model': 'project.task',
            'view_mode': 'list,kanban,form',
            'domain': [('parent_id', '=', self.task_id.id)],
            'context': {'default_parent_id': self.task_id.id, 'default_project_id': self.task_id.project_id.id},
        }

    def action_view_stock_moves(self):
        self.ensure_one()
        all_task_ids = self._get_all_task_ids()
        moves = self.env['stock.move'].search(
            [('task_id', 'in', all_task_ids)])
        picking_ids = moves.mapped('picking_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': 'Movimientos de Almacén',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', picking_ids)],
            'context': {'default_task_id': self.task_id.id},
        }

    def action_views_requisitions(self):
        self.ensure_one()
        all_task_ids = self._get_all_task_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Requisiciones',
            'res_model': 'employee.purchase.requisition',
            'view_mode': 'tree,form',
            'domain': [('task_id', 'in', all_task_ids)],
            'context': {'default_task_id': self.task_id.id},
        }

    def action_view_timesheets(self):
        self.ensure_one()
        all_task_ids = self._get_all_task_ids()
        comp_lines = self.env['compensation.line'].search(
            [('task_id', 'in', all_task_ids)])
        request_ids = comp_lines.mapped('compensation_id')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Hojas de horas',
            'res_model': 'compensation.request',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', request_ids.ids)],
            'context': {'create': False},
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        all_task_ids = self._get_all_task_ids()
        tasks = self.env['project.task'].browse(all_task_ids)
        order_ids = tasks.mapped('sale_order_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes de venta',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', order_ids)],
            'context': {'create': False},
        }

    def action_view_purchases(self):
        self.ensure_one()
        all_task_ids = self._get_all_task_ids()
        purchase_lines = self.env['purchase.order.line'].search([
            ('task_id', 'in', all_task_ids),
            ('order_id.state', 'in', ('purchase', 'done'))
        ])

        purchase_orders = purchase_lines.mapped('order_id')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes de compra',
            'res_model': 'purchase.order',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', purchase_orders.ids)],
            'context': {'default_task_order_id': self.task_id.id},
        }

    def action_view_expenses(self):
        self.ensure_one()
        all_task_ids = self._get_all_task_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gastos',
            'res_model': 'hr.expense',
            'view_mode': 'list,kanban,form',
            'domain': [('task_id', 'in', all_task_ids)],
            'context': {'default_task_id': self.task_id.id},
        }


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def action_open_task_dashboard(self):
        self.ensure_one()
        wizard = self.env['task.update'].create({'task_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': f"Tablero de {self.display_name}",
            'res_model': 'task.update',
            'view_mode': 'form',
            'res_id': wizard.id,
        }
