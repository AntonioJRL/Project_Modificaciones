from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class ProjectTaskRechazado(models.TransientModel):
    _name = 'wizard.rechazado.task'
    _description = 'Motivo de rechazo de la tarea'

    razon = fields.Text(
        string="Motivo de Rechazo",
        required=True,
    )

    def action_confirm_rechazado(self):
        active_id = self.env.context.get('active_id')
        task = self.env['project.task'].browse(active_id)
        if not task:
            raise ValidationError(_("No se encontró la tarea activa."))

        task.write({
            'approval_state': 'rejected',
            'stage_id': self.env.ref('project_modificaciones.project_task_type_obra_rejected').id,
        })
        task._mark_approval_activity_done()
        task.message_post(
            body= Markup("<b>🚫 TAREA RECHAZADA</b><br/>"
                         "<b>POR:</b> %s <br/>"
                         "<b>MOTIVO:</b> %s "
                         ) % (self.env.user.name, self.razon),
            subtype_xmlid="mail.mt_note",
        )