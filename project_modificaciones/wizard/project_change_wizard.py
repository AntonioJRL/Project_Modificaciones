from odoo import models, fields, api
from markupsafe import Markup


class ProjectChangeWizard(models.TransientModel):
    _name = 'project.change.wizard'
    _description = 'Wizard to Change Project for Multiple Tasks'

    project_id = fields.Many2one(
        'project.project', string='Proyecto Objetivo', required=True,
        help="Selecciona el proyecto objetivo al cual se reasignarán las tareas seleccionadas.")

    project_origen = fields.Many2one(
        'project.project', string='Proyecto Origen', required=True,
        help="Selecciona el proyecto origen del cual se reasignarán las tareas seleccionadas.")

    task_ids = fields.Many2many(
        'project.task', string='Tareas a Mover', required=True,
        help="Tareas seleccionadas que serán reasignadas al nuevo proyecto.")

    opciones = fields.Selection([
        ('1', 'Proyecto en Especifico'),
        ('2', 'General'),
    ], string='Opciones', required=True, default='1')

    # Método de limpieza cuando se cambia la opcion.
    @api.onchange('opciones')
    def _limpiar_project_origen(self):
        # Si se escoge la opción 1 (Proyecto en especifico limpiar las tareas seleccionada.)
        if self.opciones == '1':
            self.task_ids = False
        # Si se escoge la opción 2 (General limpiar el proyecto origen y las tareas seleccionadas.)
        if self.opciones == '2':
            self.project_origen = False
            self.task_ids = False

    def action_change_project(self):
        self.ensure_one()
        if not self.task_ids:
            return {'type': 'ir.actions.act_window_close'}

        # Colección de registros a notificar: {record: old_project_name}
        records_to_notify = {}

        # 1. Identificar todos los registros relacionados ANTES del cambio
        for task in self.task_ids:
            old_proj_name = task.project_id.name or 'Indefinido'

            # 1.1 Tarea misma
            records_to_notify[task] = old_proj_name

            # 1.2 Avances (Project Sub Update)
            for update in task.sub_update_ids:
                records_to_notify[update] = old_proj_name

            # 1.3 Gastos (HR Expense)
            if 'expense_ids' in task._fields:
                for expense in task.expense_ids:
                    records_to_notify[expense] = old_proj_name

            # 1.4 Compras (Purchase Order) - Vinculadas por task_order_id
            # Nota: Usamos sudo() para asegurar encontrar todo
            purchase_orders = self.env['purchase.order'].sudo().search([
                ('task_order_id', '=', task.id)
            ])
            for po in purchase_orders:
                records_to_notify[po] = old_proj_name

            # 1.5 Requisiciones (Employee Purchase Requisition)
            if 'requisition_ids' in task._fields:
                for req in task.requisition_ids:
                    records_to_notify[req] = old_proj_name

        # 2. Escritura masiva (Optimización)
        # Esto dispara project.task.write -> _handle_project_change que mueve los registros
        self.task_ids.write({'project_id': self.project_id.id})

        # 3. Notificación Masiva
        new_proj_name = self.project_id.name

        for record, old_proj_name in records_to_notify.items():
            # Verificar si el registro soporta message_post y sigue existiendo
            if hasattr(record, 'message_post') and record.exists():
                try:
                    record.message_post(
                        body=Markup(
                            "El Proyecto se ha cambiado a: <b>%s</b>.<br/>"
                            "Proyecto Anterior: <b>%s</b>"
                        ) % (new_proj_name, old_proj_name)
                    )
                except Exception as e:
                    # Evitar que un error de notificación rompa la transacción
                    # (Ej: registro bloqueado, permisos, etc.)
                    pass

        return {'type': 'ir.actions.act_window_close'}
