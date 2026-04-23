<<<<<<< HEAD
from odoo import fields, models

class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_control_obra_stage = fields.Boolean(
        string="Es una etapa de control de obra.",
        default=False,
        help="Marcar sí esta etapa es parte del flujo de control de obra."
=======
from odoo import fields, models

class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_control_obra_stage = fields.Boolean(
        string="Es una etapa de control de obra.",
        default=False,
        help="Marcar sí esta etapa es parte del flujo de control de obra."
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    )