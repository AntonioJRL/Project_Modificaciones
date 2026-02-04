from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    project_id = fields.Many2one(
        'project.project', string='Proyecto', index=True, copy=False)
    task_id = fields.Many2one(
        'project.task', string='Tarea', index=True, copy=False)


class StockMove(models.Model):
    _inherit = 'stock.move'

    project_id = fields.Many2one(
        'project.project', string='Proyecto', index=True, copy=False)
    task_id = fields.Many2one(
        'project.task', string='Tarea', index=True, copy=False)
