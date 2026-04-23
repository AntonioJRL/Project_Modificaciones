<<<<<<< HEAD
# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ControlCentroTrabajo(models.Model):
    _name = 'control.centro.trabajo'
    _description = 'Centro De Trabajo'

    name = fields.Char(string='Centro De Trabajo', required=True)
=======
# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ControlCentroTrabajo(models.Model):
    _name = 'control.centro.trabajo'
    _description = 'Centro De Trabajo'

    name = fields.Char(string='Centro De Trabajo', required=True)
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    cliente = fields.Many2one('res.partner', string='Contacto', required=True)