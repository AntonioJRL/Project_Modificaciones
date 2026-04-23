<<<<<<< HEAD
from odoo import api, fields, models

class ControlPlanta(models.Model):
    _name = 'control.planta'
    _description = 'Planta'

    name = fields.Char(
        string="Planta",
        required = True,
    )

    cliente = fields.Many2one(
        'res.partner',
        string="Contacto",
        required=True
=======
from odoo import api, fields, models

class ControlPlanta(models.Model):
    _name = 'control.planta'
    _description = 'Planta'

    name = fields.Char(
        string="Planta",
        required = True,
    )

    cliente = fields.Many2one(
        'res.partner',
        string="Contacto",
        required=True
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    )