from odoo import fields, models, api, _
from odoo.tools import format_amount
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class DashboardSaleOrder(models.TransientModel):
    _name = 'dashboard.sale.order'
    _description = 'Dashboard Para La Orden De Venta'

    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de Venta', required=True)
    name = fields.Char(string='Nombre', compute='_compute_name')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    # Métricas financieras
    total_revenue = fields.Monetary(
        string='Ingresos Totales', compute='_compute_financials')
    total_costs = fields.Monetary(
        string='Costos Totales', compute='_compute_financials')
    profit_margin = fields.Monetary(
        string='Margen de Ganancia', compute='_compute_financials')
    profitability_percentage = fields.Float(
        string='% Rentabilidad', compute='_compute_financials')
    total_invoiced = fields.Monetary(
        string='Facturado', compute='_compute_financials')
    total_x_invoiced = fields.Monetary(
        string='Por Facturar', compute='_compute_financials')
    total_entregado = fields.Monetary(
        string='Total Entregado', compute='_compute_financials')
    project_health = fields.Selection([
        ('good', 'Buen Estado'),
        ('warning', 'Riesgo / Advertencia'),
        ('danger', 'Peligro / Sobrecosto')
    ], string='Salud del Proyecto', compute='_compute_project_health')

    # Contenido del dashboard
    contenido = fields.Html(
        string='Contenido', compute='_compute_contenido', sanitize=False)

    ########## COMPRAS ##########
    purchase_count = fields.Integer(
        string='Órdenes de Compra', compute='_compute_purchase_data')
    purchase_total = fields.Monetary(
        string='Total Compras', compute='_compute_purchase_data')

    ########## GASTOS ##########
    expenses_count = fields.Integer(
        string='Gastos', compute='_compute_expenses_data')
    expenses_total = fields.Monetary(
        string='Total Gastos', compute='_compute_expenses_data')

    ########## LINEAS DE VENTA ##########
    sale_order_line_ids = fields.One2many('sale.order.line', related='sale_order_id.order_line',
                                          string='Líneas de Orden de Venta', readonly=True)
    lines_count = fields.Integer(
        string='Número de Líneas', compute='_compute_lines_data')
    lines_total = fields.Monetary(
        string='Total Líneas', compute='_compute_lines_data')

    ########## REQUISICIONES ##########
    requisition_count = fields.Integer(
        string='Requisiciones', compute='_compute_requisition_count')

    ########## MOVIMIENTOS ALMACEN ##########
    stock_move_count = fields.Integer(
        string='Movimientos Almacén', compute='_compute_stock_move_data')
    stock_move_cost = fields.Monetary(
        string='Costo Mov. Almacén', compute='_compute_stock_move_data')

    ########## AVANCES ##########
    avances_count = fields.Integer(
        string='Número de Avances', compute='_compute_avances_data')
    avances_progress = fields.Float(
        string='Progreso Total', compute='_compute_avances_data')
    avances_units_delivered = fields.Float(
        string='Unidades Entregadas', compute='_compute_avances_data')
    avances_units_missing = fields.Float(
        string='Unidades Faltantes', compute='_compute_avances_data')
    avances_value_delivered = fields.Monetary(
        string='Valor Entregado', compute='_compute_avances_data')
    avances_value_expected = fields.Monetary(
        string='Valor Esperado', compute='_compute_avances_data')

    ######### HOJAS DE HORAS ##########
    time_sheet_count = fields.Integer(
        string='Número de Hojas de Horas', compute='_compute_time_sheet_data')
    time_sheet_total = fields.Monetary(
        string='Total Hojas de Horas', compute='_compute_time_sheet_data')

    def _get_task_ids(self):
        self.ensure_one()
        return self.env['project.task'].search([('sale_order_id', '=', self.sale_order_id.id)])

    @api.depends('sale_order_id')
    def _compute_name(self):
        for wizard in self:
            sale_name = wizard.sale_order_id.display_name if wizard.sale_order_id else ''
            wizard.name = f"Dashboard {sale_name}" if sale_name else 'Dashboard'

    @api.depends('sale_order_id', 'total_revenue', 'total_costs', 'total_invoiced', 'total_x_invoiced',
                 'profit_margin', 'profitability_percentage', 'purchase_count', 'purchase_total',
                 'expenses_count', 'expenses_total', 'lines_count', 'lines_total', 'requisition_count',
                 'stock_move_count', 'stock_move_cost', 'avances_count', 'avances_progress',
                 'time_sheet_count', 'time_sheet_total')
    def _compute_contenido(self):
        for wizard in self:
            avances_data = []
            if (wizard.sale_order_id and hasattr(wizard.sale_order_id, 'project_sub_updates')):
                for avance in wizard.sale_order_id.project_sub_updates:
                    avances_data.append({
                        'name': avance.name or 'N/A',
                        'producto': avance.producto.name if avance.producto else 'Sin producto',
                        'unit_progress': avance.unit_progress or 0,
                        'sale_current': avance.sale_current or 0,
                        'ct': avance.ct.name if avance.ct.name else 'Sin Centro Trabajo',
                        'actual_progress': avance.actual_progress or 0,
                        'date': avance.date or 'Sin fecha',
                    })

            lines_data = []
            if wizard.sale_order_id:
                for line in wizard.sale_order_id.order_line:
                    lines_data.append({
                        'id': line.id,
                        'name': line.name,
                        'product_uom_qty': line.product_uom_qty,
                        'progress_percentage': line.progress_percentage,
                        'qty_delivered': line.qty_delivered,
                        'qty_invoiced': line.qty_invoiced,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_subtotal,
                        'estado': line.state,
                        'avances_count': len(line.avances_ids) if hasattr(line, 'avances_ids') else 0,
                    })

            timesheets_data = []
            if wizard.sale_order_id:
                task_ids = wizard._get_task_ids()
                timesheets = self.env['account.analytic.line'].search(
                    [('task_id', 'in', task_ids.ids)])
                for ts in timesheets:
                    timesheets_data.append({
                        'date': ts.date or 'Sin fecha',
                        'employee': ts.employee_id.name if ts.employee_id else 'Sin empleado',
                        'task': ts.task_id.name if ts.task_id else 'Sin tarea',
                        'description': ts.name or 'Sin descripción',
                        'hours': ts.unit_amount or 0.0,
                        'cost': abs(ts.amount) or 0.0,
                    })

            import json
            costs_chart_data = json.dumps({
                'labels': ['Compras', 'Gastos', 'Hojas de Horas'],
                'datasets': [{
                    'data': [wizard.purchase_total or 0, wizard.expenses_total or 0, wizard.time_sheet_total or 0],
                    'backgroundColor': ['#ff6384', '#36a2eb', '#ffce56'],
                }]
            })

            values = {
                'sale_order': wizard.sale_order_id,
                'project_health': wizard.project_health,
                'costs_chart_data': costs_chart_data,
                'financials': {
                    'revenue': wizard.total_revenue,
                    'costs': wizard.total_costs,
                    'invoiced': wizard.total_invoiced,
                    'x_invoiced': wizard.total_x_invoiced,
                    'profit_margin': wizard.profit_margin,
                    'profitability_percentage': wizard.profitability_percentage,
                    'entregado': wizard.total_entregado,
                },
                'metrics': {
                    'purchase_count': wizard.purchase_count,
                    'purchase_total': wizard.purchase_total,
                    'expenses_count': wizard.expenses_count,
                    'expenses_total': wizard.expenses_total,
                    'lines_count': wizard.lines_count,
                    'lines_total': wizard.lines_total,
                    'requisition_count': wizard.requisition_count,
                    'stock_move_count': wizard.stock_move_count,
                    'stock_move_cost': wizard.stock_move_cost,
                    'avances_count': wizard.avances_count,
                    'avances_progress': wizard.avances_progress,
                    'avances_units_delivered': getattr(wizard, 'avances_units_delivered', 0),
                    'avances_units_missing': getattr(wizard, 'avances_units_missing', 0),
                    'avances_value_delivered': getattr(wizard, 'avances_value_delivered', 0),
                    'avances_value_expected': getattr(wizard, 'avances_value_expected', 0),
                    'time_sheet_count': wizard.time_sheet_count,
                    'time_sheet_total': wizard.time_sheet_total,
                },
                'format_monetary': lambda v: format_amount(self.env, v or 0.0, wizard.currency_id),
                'format_percentage': lambda v: f"{v or 0.0:.2f}%",
                'format_unit': lambda v: f"{v or 0.0:.4f}",
                'current_date': datetime.now().strftime("%d/%m/%Y"),
                'avances_list': avances_data,
                'lines_list': lines_data,
                'timesheets_list': timesheets_data,
            }

            wizard.contenido = self.env['ir.qweb']._render(
                'project_modificaciones.sale_order_dashboard_template', values)

    @api.depends('sale_order_line_ids.qty_delivered', 'sale_order_line_ids.price_unit',
                 'sale_order_line_ids.qty_invoiced', 'purchase_total', 'expenses_total', 'time_sheet_total',
                 'sale_order_id.amount_untaxed')
    def _compute_financials(self):
        for wizard in self:
            total_entregado = sum(
                line.qty_delivered * line.price_unit for line in wizard.sale_order_line_ids)
            total_revenue = wizard.sale_order_id.amount_untaxed if wizard.sale_order_id else 0.0
            total_costs = (wizard.purchase_total or 0) + \
                (wizard.expenses_total or 0) + (wizard.time_sheet_total or 0)
            total_invoiced = sum(
                line.qty_invoiced * line.price_unit for line in wizard.sale_order_line_ids)
            total_x_invoiced = sum((line.qty_delivered - line.qty_invoiced)
                                   * line.price_unit for line in wizard.sale_order_line_ids)
            profit_margin = total_entregado - total_costs
            profitability_percentage = (
                profit_margin / total_entregado * 100) if total_entregado > 0 else 0.0

            wizard.total_entregado = total_entregado
            wizard.total_revenue = total_revenue
            wizard.total_costs = total_costs
            wizard.total_invoiced = total_invoiced
            wizard.total_x_invoiced = total_x_invoiced
            wizard.profit_margin = profit_margin
            wizard.profitability_percentage = profitability_percentage

    @api.depends('profit_margin', 'avances_progress', 'total_invoiced', 'total_revenue')
    def _compute_project_health(self):
        for record in self:
            health = 'good'
            if record.profit_margin < 0:
                health = 'danger'
            elif record.avances_progress > 80 and (record.total_invoiced / record.total_revenue if record.total_revenue else 0) < 0.2:
                health = 'danger'
            elif record.profit_margin < (record.total_revenue * 0.15):
                health = 'warning'
            elif record.avances_progress > 50 and record.total_invoiced == 0:
                health = 'warning'
            record.project_health = health

    @api.depends('sale_order_id')
    def _compute_purchase_data(self):
        for record in self:
            count = 0
            total = 0.0
            if record.sale_order_id:
                task_ids = record._get_task_ids()
                domain = [('task_id', 'in', task_ids.ids)]
                lines = self.env['purchase.order.line'].search(domain)
                count = len(lines.mapped('order_id'))
                valid_lines = lines.filtered(
                    lambda l: l.order_id.state in ('purchase', 'done'))
                total = sum(valid_lines.mapped('price_subtotal'))
            record.purchase_count = count
            record.purchase_total = total

    @api.depends('sale_order_id')
    def _compute_expenses_data(self):
        for record in self:
            count = 0
            total = 0.0
            if record.sale_order_id:
                task_ids = record._get_task_ids()
                expenses = self.env['hr.expense'].search(
                    [('task_id', 'in', task_ids.ids)])
                count = len(expenses)
                valid_expenses = expenses.filtered(
                    lambda e: e.state in ('approved', 'done'))
                total = sum(valid_expenses.mapped('total_amount'))
            record.expenses_count = count
            record.expenses_total = total

    @api.depends('sale_order_id', 'sale_order_id.order_line', 'sale_order_id.amount_untaxed')
    def _compute_lines_data(self):
        for record in self:
            record.lines_count = len(
                record.sale_order_id.order_line) if record.sale_order_id else 0
            record.lines_total = record.sale_order_id.amount_untaxed if record.sale_order_id else 0.0

    @api.depends('sale_order_id')
    def _compute_requisition_count(self):
        for record in self:
            count = 0
            if record.sale_order_id:
                task_ids = record._get_task_ids()
                if task_ids:
                    count = self.env['employee.purchase.requisition'].search_count(
                        [('task_id', 'in', task_ids.ids)])
            record.requisition_count = count

    @api.depends('sale_order_id')
    def _compute_stock_move_data(self):
        for record in self:
            count = 0
            cost = 0.0
            if record.sale_order_id:
                tasks = record._get_task_ids()
                if tasks:
                    count = sum(tasks.mapped('stock_move_count'))
                    cost = sum(tasks.mapped('stock_move_cost'))
            record.stock_move_count = count
            record.stock_move_cost = cost

    @api.depends('sale_order_id', 'sale_order_id.project_sub_updates')
    def _compute_avances_data(self):
        for record in self:
            avances_progress = 0.0
            avances_units_delivered = 0.0
            avances_units_missing = 0.0
            avances_value_delivered = 0.0
            avances_value_expected = 0.0
            avances_count = 0

            if record.sale_order_id and hasattr(record.sale_order_id, 'project_sub_updates') and record.sale_order_id.project_sub_updates:
                avances = record.sale_order_id.project_sub_updates
                for avance in avances:
                    avances_count += 1

                total_qty_expected = sum(
                    record.sale_order_id.order_line.mapped('product_uom_qty'))
                total_units_delivered = sum(
                    record.sale_order_id.order_line.mapped('qty_delivered'))

                total_valor_entregado = sum(
                    line.qty_delivered * line.price_unit for line in record.sale_order_line_ids)

                if total_qty_expected > 0:
                    avances_progress = (
                        total_units_delivered / total_qty_expected) * 100

                avances_units_delivered = total_units_delivered
                avances_units_missing = total_qty_expected - total_units_delivered
                avances_value_delivered = total_valor_entregado
                avances_value_expected = record.sale_order_id.amount_untaxed or 0.0

            record.avances_progress = avances_progress
            record.avances_units_delivered = avances_units_delivered
            record.avances_units_missing = avances_units_missing
            record.avances_value_delivered = avances_value_delivered
            record.avances_value_expected = avances_value_expected
            record.avances_count = avances_count

    @api.depends('sale_order_id')
    def _compute_time_sheet_data(self):
        for record in self:
            count = 0
            total = 0.0
            if record.sale_order_id:
                task_ids = record._get_task_ids()
                timesheets = self.env['account.analytic.line'].search(
                    [('task_id', 'in', task_ids.ids)])
                count = len(timesheets)
                total = abs(sum(timesheets.mapped('amount')))
            record.time_sheet_count = count
            record.time_sheet_total = total

    def action_view_purchase_orders(self):
        self.ensure_one()
        if self.sale_order_id:
            task_ids = self._get_task_ids()
            purchase_order_lines = self.env['purchase.order.line'].search(
                [('task_id', 'in', task_ids.ids)])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Órdenes de Compra Relacionadas',
                'res_model': 'purchase.order.line',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', purchase_order_lines.ids)],
                'context': {'create': False},
            }
        return False

    def action_view_expenses_count(self):
        self.ensure_one()
        if self.sale_order_id:
            task_ids = self._get_task_ids()
            expenses = self.env['hr.expense'].search(
                [('task_id', 'in', task_ids.ids)])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Gastos Relacionados',
                'res_model': 'hr.expense',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', expenses.ids)],
                'context': {'create': False},
            }
        return False

    def action_view_sale_order_lines(self):
        self.ensure_one()
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Líneas de Orden de Venta',
                'res_model': 'sale.order.line',
                'view_mode': 'tree,form',
                'domain': [('order_id', '=', self.sale_order_id.id)],
                'context': {'create': False},
            }
        return False

    def action_view_requisitions(self):
        self.ensure_one()
        if self.sale_order_id:
            task_ids = self._get_task_ids()
            return {
                'type': 'ir.actions.act_window',
                'name': 'Requisiciones Relacionadas',
                'res_model': 'employee.purchase.requisition',
                'view_mode': 'tree,form',
                'domain': [('task_id', 'in', task_ids.ids)],
                'context': {'create': False},
            }
        return False

    def action_view_stock_moves(self):
        self.ensure_one()
        if self.sale_order_id:
            task_ids = self._get_task_ids()
            return {
                'type': 'ir.actions.act_window',
                'name': 'Movimientos de Almacén',
                'res_model': 'stock.move',
                'view_mode': 'tree,form',
                'domain': [('task_id', 'in', task_ids.ids), ('state', '=', 'done'), ('picking_type_id.code', '=', 'outgoing')],
                'context': {'create': False},
            }
        return False

    def action_view_avances_dashboard(self):
        self.ensure_one()
        if self.sale_order_id:
            return {
                'name': _('Avances'),
                'type': 'ir.actions.act_window',
                'res_model': 'project.sub.update',
                'view_mode': 'tree,form',
                'domain': [('sale_order_id', '=', self.sale_order_id.id)],
                'context': {'default_sale_order_id': self.sale_order_id.id, 'create': False},
            }
        return

    def action_view_avances_from_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Avances de Línea',
            'res_model': 'project.sub.update',
            'view_mode': 'tree,form',
            'domain': [('sale_order_line_id', '=', self.id)],
            'context': {
                'default_sale_order_line_id': self.id,
                'search_default_sale_order_line_id': self.id
            },
            'target': 'current',
        }

    def action_view_timesheets(self):
        self.ensure_one()
        if self.sale_order_id:
            task_ids = self._get_task_ids()
            timesheets = self.env['account.analytic.line'].search(
                [('task_id', 'in', task_ids.ids)])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Hojas de Horas Relacionadas',
                'res_model': 'account.analytic.line',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', timesheets.ids)],
                'context': {'create': False},
            }
        return False

    def action_print_dashboard(self):
        self.ensure_one()
        return self.env.ref('project_modificaciones.action_report_dashboard_sale_order').report_action(self)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_open_sale_dashboard(self):
        self.ensure_one()
        wizard = self.env['dashboard.sale.order'].search(
            [('sale_order_id', '=', self.id)], limit=1)
        if not wizard:
            wizard = self.env['dashboard.sale.order'].create(
                {'sale_order_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': f"Dashboard - {self.display_name}",
            'res_model': 'dashboard.sale.order',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'current',
        }
