from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import Markup
import logging
import json

_logger = logging.getLogger(__name__)


class ProjectReclassifyWizard(models.TransientModel):
    _name = 'project.reclassify.wizard'
    _description = 'Asistente de Reclasificación'

    project_id = fields.Many2one(
        'project.project', string='Nuevo Proyecto',
        help="Selecciona el proyecto al cual se moverán los registros seleccionados.")

    task_id = fields.Many2one(
        'project.task', string='Nueva Tarea',
        domain="[('project_id', '=', project_id)]",
        help="Selecciona la tarea destino (opcional).")

    analytic_distribution = fields.Json(
        string='Distribución Analítica',
        help="Nueva distribución analítica a asignar. Si se deja vacío, se mantendrá la actual.")

    analytic_precision = fields.Integer(
        store=False, default=2)

    # --- LISTAS DE TRABAJO (Registros a procesar) ---

    # 1. Compras
    purchase_line_ids = fields.Many2many(
        'purchase.order.line', string='Líneas de Compra')

    # 2. Compensaciones
    compensation_line_ids = fields.Many2many(
        'compensation.line', string='Líneas de Compensación')

    # 3. Requisiciones
    requisition_line_ids = fields.Many2many(
        'requisition.order', string='Líneas de Requisición')

    # 4. Gastos
    expense_line_ids = fields.Many2many(
        'hr.expense', string='Gastos')

    # 5. Stock
    stock_move_ids = fields.Many2many(
        'stock.move', string='Movimientos de Stock')

    # 6. Apuntes Contables (Account Move Lines)
    move_line_ids = fields.Many2many(
        'account.move.line', string='Apuntes Contables')

    # 7. Líneas Analíticas (Timesheets / Costos)
    analytic_line_ids = fields.Many2many(
        'account.analytic.line', string='Líneas Analíticas')

    @api.model
    def default_get(self, fields):
        res = super(ProjectReclassifyWizard, self).default_get(fields)
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids')

        if active_model and active_ids:
            records = self.env[active_model].browse(active_ids)

            # --- POPULAR LISTAS DE TRABAJO (Work Lists) ---

            # 1. Compras
            if active_model == 'purchase.order':
                # De Cabecera a Líneas
                all_lines = records.mapped('order_line')
                res['purchase_line_ids'] = [(6, 0, all_lines.ids)]
            elif active_model == 'purchase.order.line':
                # De Líneas a Líneas
                res['purchase_line_ids'] = [(6, 0, active_ids)]

            # 2. Compensaciones
            elif active_model == 'compensation.request':
                all_lines = records.mapped('compensation_line_ids')
                res['compensation_line_ids'] = [(6, 0, all_lines.ids)]
            elif active_model == 'compensation.line':
                res['compensation_line_ids'] = [(6, 0, active_ids)]

            # 3. Requisiciones de Empleado
            elif active_model == 'employee.purchase.requisition':
                all_lines = records.mapped('requisition_order_ids')
                res['requisition_line_ids'] = [(6, 0, all_lines.ids)]
            elif active_model == 'requisition.order':
                res['requisition_line_ids'] = [(6, 0, active_ids)]

            # 4. Gastos
            elif active_model == 'hr.expense.sheet':
                all_lines = records.mapped('expense_line_ids')
                res['expense_line_ids'] = [(6, 0, all_lines.ids)]
            elif active_model == 'hr.expense':
                res['expense_line_ids'] = [(6, 0, active_ids)]

            # 5. Stock / Albaranes
            elif active_model == 'stock.picking':
                all_lines = records.mapped('move_ids')
                res['stock_move_ids'] = [(6, 0, all_lines.ids)]
            elif active_model == 'stock.move':
                res['stock_move_ids'] = [(6, 0, active_ids)]

            # 6. Asientos Contables (Account Move) -> Apuntes (Move Line)
            elif active_model == 'account.move':
                # Mostrar todas las líneas del asiento
                all_lines = records.mapped('line_ids')
                res['move_line_ids'] = [(6, 0, all_lines.ids)]
            elif active_model == 'account.move.line':
                res['move_line_ids'] = [(6, 0, active_ids)]

            # 7. Líneas Analíticas (Timesheets)
            elif active_model == 'account.analytic.line':
                res['analytic_line_ids'] = [(6, 0, active_ids)]

        return res
        # Forzar manual porque venimos de líneas
        res['selection_type_compensation'] = 'manual'

        return res

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.task_id = False
            # Opcional: Si el proyecto tiene cuenta analítica por defecto, ¿sobreescribimos?
            # Mejor no, respetamos lo que venga del registro original (pre-filled in default_get)
            # a menos que esté vacío.
            if not self.analytic_distribution and self.project_id.analytic_account_id:
                self.analytic_distribution = {
                    str(self.project_id.analytic_account_id.id): 100}

    def action_reclassify(self):
        """
        Ejecuta la reclasificación basada en las listas de trabajo pobladas en el wizard.
        """
        # 1. Compras
        if self.purchase_line_ids:
            self._reclassify_purchase_lines(self.purchase_line_ids)

        # 2. Compensaciones (Líneas)
        if self.compensation_line_ids:
            self._reclassify_compensation_lines(self.compensation_line_ids)

        # 3. Requisiciones
        if self.requisition_line_ids:
            self._reclassify_requisition_lines(self.requisition_line_ids)

        # 4. Gastos
        if self.expense_line_ids:
            self._reclassify_expenses(self.expense_line_ids)

        # 5. Stock Moves
        if self.stock_move_ids:
            self._reclassify_stock_moves(self.stock_move_ids)

        # 6. Apuntes Contables
        if self.move_line_ids:
            self._reclassify_account_move_lines(self.move_line_ids)

        # 7. Líneas Analíticas
        if self.analytic_line_ids:
            self._reclassify_analytic_lines(self.analytic_line_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reclasificación Completada'),
                'message': _('Los registros han sido reclasificados exitosamente.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _log_chatter(self, records):
        """Intenta dejar un mensaje en el chatter de los registros si soportan mail.thread"""
        # Usamos Markup de odoo.tools para asegurar que no se escape el HTML
        msg = Markup("<b>%s</b><br/>%s: %s<br/>") % (
            _("Reclasificación"),
            _("Nuevo Proyecto"),
            self.project_id.name
        )

        if self.task_id:
            msg += Markup("%s: %s<br/>") % (_("Nueva Tarea"),
                                            self.task_id.name)

        if self.analytic_distribution:
            msg += Markup("%s: %s<br/>") % (_("Nueva Analítica"),
                                            _("Distribución Actualizada"))

        for record in records:
            if hasattr(record, 'message_post'):
                try:
                    record.message_post(body=msg)
                except Exception:
                    continue  # Si falla el log, no detener el proceso

    def _compute_new_distribution(self, current_dist):
        """
        Fusiona la distribución proporcionada por el usuario con la distribución actual basada en PLANES.
        Si el asistente proporciona una cuenta para el Plan X, reemplaza cualquier cuenta existente para el Plan X.
        Las cuentas existentes para el Plan Y(no presente en el asistente) se conservan.
        """
        if not self.analytic_distribution:
            return current_dist or {}

        wizard_dist = self.analytic_distribution
        current_dist = current_dist or {}

        # 1. Analizar Distribución del Asistente (El nuevo estado)
        # Extraer Planes cubiertos por el asistente
        wizard_account_ids = set()
        for key in wizard_dist.keys():
            parts = key.split(',')
            for p in parts:
                if p.isdigit():
                    wizard_account_ids.add(int(p))

        wizard_accounts = self.env['account.analytic.account'].sudo().browse(
            list(wizard_account_ids))
        wizard_plans = {acc.plan_id.id for acc in wizard_accounts}

        # 2. Analizar Distribución Actual
        # Necesitamos deconstruir claves, filtrar cuentas que pertenecen a "Planes del Asistente", y mantener otras.
        # Problema: Las claves de distribución coinciden con porcentajes.
        # Estrategia:
        # A) Si el asistente tiene una clave única 'B': 100. Y el actual tiene 'A,X': 100.
        #    Queremos 'B,X': 100.
        #    Combinación simple de cuentas.

        # Ruta rápida: Si el asistente está vacío, devolver actual. (Manejado arriba)

        # B) Recopilar "Cuentas a mantener" de la actual
        # Dado que podríamos tener varias líneas en la distribución (ej. 50% Proyecto A, 50% Proyecto B),
        # esta lógica de fusión es complicada para divisiones complejas.
        # SIMPLIFICACIÓN: Asumimos que estamos aplicando la distribución del Asistente (100%) a toda la línea,
        # mezclando las "Otras Dimensiones" encontradas en la línea actual.
        # ¿Pero si la línea actual estaba dividida 50/50, cómo fusionamos?
        # El usuario generalmente quiere mover TODA la línea al nuevo Proyecto.
        # Así que tomamos la Distribución del Asistente (porcentajes) como BASE,
        # ¿y adjuntamos las "Cuentas Preservadas" a cada clave en la distribución del Asistente?

        # Probemos:
        # Actual: {'A,X': 50, 'A,Y': 50}  (A=Proy, X/Y=Deptos)
        # Asistente:  {'B': 100} (B=Nuevo Proy)
        # Objetivo:    {'B,X': 50, 'B,Y': 50} ?? O {'B,X': 50, 'B,Y': 50}
        # Esto mantiene la estructura de división del Actual, reemplazando A con B.

        # Algoritmo:
        # Iterar Ítems Actuales.
        # Para cada Clave/Porcentaje:
        #   Analizar Cuentas.
        #   Filtrar cuentas que pertenecen a Planes del Asistente.
        #   Agregar Cuentas del Asistente (Espera, ¿cuáles? ¿El asistente podría tener múltiples?)
        #   Si el Asistente tiene múltiples entradas (ej. 50% B1, 50% B2), ¿cómo combinamos con Actual (50% X, 50% Y)?
        #   ¿Producto cartesiano? Eso es desordenado.

        # Enfoque Pragmático (Lógica de Reclasificación Estándar Odoo):
        # Usualmente la reclasificación apunta a un Proyecto específico (1 cuenta).
        # Si el Asistente tiene >1 entradas, es ambiguo cómo fusionar con divisiones existentes.
        # Suposición: El Asistente generalmente tiene 1 Cuenta de Proyecto (100%).

        # Algoritmo Revisado:
        # 1. Identificar "Cuentas Preservadas" de la Actual (Cuentas NO en Planes del Asistente).
        #    Nota: Si la Actual tiene división (X 50%, Y 50%), efectivamente tenemos dos conjuntos de cuentas preservadas.
        # 2. Si el Asistente tiene distribución simple del 100%:
        #    ¿Aplicar ese 100% a cada línea de división existente?
        #    No, preservar los porcentajes de división existentes.
        #    Actual: {'A,X': 50, 'A,Y': 50} -> Eliminar A. Mantener X (50), Y (50).
        #    ¿Agregar B a ambos? -> {'B,X': 50, 'B,Y': 50}. SÍ.

        # ¿Qué pasa si el Asistente MISMO está dividido? {'B1': 50, 'B2': 50}.
        # Actual: {'X': 100}.
        # Resultado: {'B1,X': 50, 'B2,X': 50}. (Cartesiano)

        # Implementación de Mezcla Cartesiana:

        new_result = {}

        # Pre-fetch all involved accounts for plan checking
        current_account_ids = set()
        for key in current_dist.keys():
            for p in key.split(','):
                if p.isdigit():
                    current_account_ids.add(int(p))

        all_accounts = self.env['account.analytic.account'].sudo().browse(
            list(current_account_ids | wizard_account_ids))
        plan_map = {acc.id: acc.plan_id.id for acc in all_accounts}

        # Helper to filter accounts from a key
        def get_preserved_accounts(key_str):
            preserved = []
            for p in key_str.split(','):
                if p.isdigit():
                    aid = int(p)
                    # If this account's plan is NOT in the plans touched by wizard, keep it
                    if plan_map.get(aid) not in wizard_plans:
                        preserved.append(aid)
            return preserved

        # Iterar Asistente (Bucle Externo) - porque el Asistente dicta la nueva estructura "Principal"/división
        # Alguna clave de ítem del asistente se mezcla con Alguna clave de ítem actual
        # No, eso multiplica porcentaje = 100% * 100% = 10000%
        # Necesitamos normalizar.

        # Let's look at the User's likely case:
        # Current: Single line 100%. Wizard: Single line 100%.
        # Merge: Combine accounts. return {'A,B': 100}.

        # Logic:
        # Iterate Current Dist.
        # For each item (Key, Pct):
        #   Get Preserved Accounts (P).
        #   We want to attach the Wizard's Accounts (W) to this.
        #   If Wizard is 100% 'W', result is 'P+W': Pct.
        #   If Wizard is split {'W1': 60, 'W2': 40}?
        #   Then we split this current item too?
        #   (Pct * WizardPct/100)?
        #   Current: {X: 100}. Wizard {W1: 60, W2: 40}.
        #   Result: {X,W1: 60}, {X,W2: 40}.

        for w_key, w_val in wizard_dist.items():
            w_accs = [int(x) for x in w_key.split(',') if x.isdigit()]
            w_pct = w_val

            for c_key, c_val in current_dist.items():
                preserved = get_preserved_accounts(c_key)

                # Combine
                combined = sorted(list(set(preserved + w_accs)))
                if not combined:
                    continue

                new_key = ",".join(str(x) for x in combined)

                # Nuevo Porcentaje = Ptc Actual * (Pct Asistente / 100) basado en base típica 100
                # En realidad analytic_distribution de Odoo suma 100.
                # Así que sí, multiplicar factores.
                new_pct = (c_val * w_pct) / 100.0

                new_result[new_key] = new_result.get(new_key, 0.0) + new_pct

        # Rounding cleanup
        return {k: v for k, v in new_result.items() if v > 0.01}

    def _reclassify_requisition_line(self, lines):
        """Intenta dejar un mensaje en el chatter de los registros si soportan mail.thread"""
        # Usamos Markup de odoo.tools para asegurar que no se escape el HTML
        msg = Markup("<b>%s</b><br/>%s: %s<br/>") % (
            _("Reclasificación"),
            _("Nuevo Proyecto"),
            self.project_id.name
        )

        if self.task_id:
            msg += Markup("%s: %s<br/>") % (_("Nueva Tarea"),
                                            self.task_id.name)

        if self.analytic_distribution:
            msg += Markup("%s: %s<br/>") % (_("Nueva Analítica"),
                                            _("Distribución Actualizada"))

        for record in lines:  # Error variable 'records' corrected to 'lines' or iterate passed records
            # NOTE: Logic error in original code: _reclassify_requisition_line(self, lines) used 'records' loop but 'records' undefined.
            # Assuming typical chatter pattern.
            if hasattr(record, 'message_post'):
                try:
                    record.message_post(body=msg)
                except Exception:
                    continue

    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # LÓGICA ESPECÍFICA POR MODELO (Work List Pattern)
    # -------------------------------------------------------------------------

    def _reclassify_purchase_lines(self, lines, skip_models=None):
        """Líneas de Compra: Proyecto, Tarea y Analítica + Cascada"""
        skip_models = skip_models or []
        skip_models.append('purchase.order.line')

        # 1. Actualizar Líneas
        vals = {}
        if self.project_id:
            vals['project_id'] = self.project_id.id
        if self.task_id:
            vals['task_id'] = self.task_id.id

        if self.analytic_distribution:
            for line in lines:
                curr = dict(line.analytic_distribution or {})
                new_d = self._compute_new_distribution(curr)
                line.write({'analytic_distribution': new_d})

        if vals:
            lines.write(vals)

        # Log en headers únicos + Actualizar Cabecera (Sincronización)
        unique_orders = lines.mapped('order_id')

        for order in unique_orders:
            # Sincronizar Cabecera
            valid_lines = order.order_line.filtered(
                lambda l: not l.display_type)
            if valid_lines:
                projects = valid_lines.mapped('project_id')
                tasks = valid_lines.mapped('task_id')

                header_vals = {}
                # Proyecto
                if len(projects) == 1:
                    header_vals['project_id'] = projects[0].id
                elif len(projects) > 1:
                    header_vals['project_id'] = False

                # Tarea (task_order_id en header vs task_id en linea)
                if len(tasks) == 1:
                    header_vals['task_order_id'] = tasks[0].id
                elif len(tasks) > 1:
                    header_vals['task_order_id'] = False

                if header_vals:
                    order.write(header_vals)

        self._log_chatter(unique_orders)

        # 2. Cascada: Movimientos de Stock (move_ids field in PO Line)
        if 'stock.move' not in skip_models:
            # Intentar usar el campo One2many standard 'move_ids' si existe para ser más precisos
            moves = self.env['stock.move']
            if hasattr(lines, 'move_ids'):
                moves = lines.mapped('move_ids')
            else:
                moves = self.env['stock.move'].search(
                    [('purchase_line_id', 'in', lines.ids)])

            if moves:
                # Debug info
                # self._log_chatter(moves.mapped('picking_id'))
                self._reclassify_stock_moves(moves, skip_models=skip_models)

        # 3. Cascada: Líneas de Factura (linked via purchase_line_id)
        if 'account.move.line' not in skip_models:
            inv_lines = self.env['account.move.line'].search([
                ('purchase_line_id', 'in', lines.ids)
            ])
            if inv_lines:
                self._reclassify_account_move_lines(
                    inv_lines, skip_models=skip_models)

        # 4. Cascada: Requisiciones (Búsqueda por coincidencia)
        for line in lines:
            req_lines = self._find_related_requisition_lines(line)
            if req_lines:
                self._reclassify_requisition_lines(req_lines)

    def _find_related_requisition_lines(self, po_line):
        """Helper para encontrar líneas de requisición vinculadas a una línea de compra"""
        order = po_line.order_id
        req_header_ids = set()

        # 1. Enlace directo en línea
        if hasattr(po_line, 'req_ids') and po_line.req_ids:
            req_header_ids.update(po_line.req_ids.ids)

        # 2. Enlace en cabecera
        if not req_header_ids:
            try:
                if hasattr(order, 'requisition_id2') and order.requisition_id2:
                    req_header_ids.add(order.requisition_id2.id)
                if hasattr(order, 'requisition_ids') and order.requisition_ids:
                    req_header_ids.update(order.requisition_ids.ids)
            except Exception:
                pass

        if req_header_ids:
            domain = [
                ('requisition_product_id', 'in', list(req_header_ids)),
                ('product_id', '=', po_line.product_id.id)
            ]
            return self.env['requisition.order'].search(domain)
        return self.env['requisition.order']

    def _reclassify_stock_moves(self, moves, skip_models=None):
        """Movimientos de Stock (Líneas)"""
        skip_models = skip_models or []
        skip_models.append('stock.move')
        vals = {}
        if self.project_id:
            vals['project_id'] = self.project_id.id
        if self.task_id:
            vals['task_id'] = self.task_id.id

        if vals:
            moves.write(vals)

        # Sincronizar Cabecera (Picking)
        pickings = moves.mapped('picking_id')
        for picking in pickings:
            # Filtrar moves validos (no cancelados o según lógica negocio)
            # En stock.move no hay display_type, asi que usamos todos
            all_moves = picking.move_ids
            if all_moves:
                projects = all_moves.mapped('project_id')
                tasks = all_moves.mapped('task_id')

                header_vals = {}
                # Proyecto
                if len(projects) == 1:
                    header_vals['project_id'] = projects[0].id
                elif len(projects) > 1:
                    header_vals['project_id'] = False

                # Tarea
                if len(tasks) == 1:
                    header_vals['task_id'] = tasks[0].id
                elif len(tasks) > 1:
                    header_vals['task_id'] = False

                if header_vals:
                    picking.write(header_vals)

    def _reclassify_analytic_lines(self, lines):
        """Hojas de Horas / Costos"""
        vals = {}
        if self.project_id:
            vals['project_id'] = self.project_id.id
        if self.task_id:
            vals['task_id'] = self.task_id.id

        if self.analytic_distribution:
            # Try to extract single account from distribution for TS (legacy account_id)
            first_dist = self.analytic_distribution
            if first_dist:
                for key in first_dist.keys():
                    if ',' not in key and key.isdigit():
                        vals['account_id'] = int(key)
                        break

        if vals:
            lines.write(vals)

    def _reclassify_requisition_lines(self, lines):
        """Reclasifica Líneas de Requisición"""
        vals = {}
        if self.project_id:
            vals['project_id'] = self.project_id.id
        if self.task_id:
            vals['task_id'] = self.task_id.id

        if self.analytic_distribution:
            # Requisiciones suelen usar account_analytic_id (m2o) o analytic_distribution (json)
            # Asumimos soporte para ambos o prioridad
            if 'analytic_distribution' in lines._fields:
                for line in lines:
                    curr = dict(line.analytic_distribution or {})
                    new_d = self._compute_new_distribution(curr)
                    line.write({'analytic_distribution': new_d})

            elif 'account_analytic_id' in lines._fields:
                # Legacy m2o field
                first_dist = self.analytic_distribution
                if first_dist:
                    for key in first_dist.keys():
                        if ',' not in key and key.isdigit():
                            vals['account_analytic_id'] = int(key)
                            break

        if vals:
            lines.write(vals)

        unique_reqs = lines.mapped('requisition_id')
        self._log_chatter(unique_reqs)

    def _reclassify_account_move_lines(self, lines, skip_models=None):
        """Apuntes Contables: Distribución Analítica + Líneas Analíticas (Impacto)"""
        skip_models = skip_models or []
        skip_models.append('account.move.line')

        # A) Aplicar cambios locales (Analítica)
        if self.analytic_distribution:
            for line in lines:
                # 1. Usar la distribución nueva directamente (SMART MERGE)
                current_dist = dict(line.analytic_distribution or {})
                new_dist = self._compute_new_distribution(current_dist)

                # ORM Directo
                line.write({'analytic_distribution': new_dist})
                line.invalidate_recordset(['analytic_distribution'])

                # 2. Actualizar Líneas Analíticas (account.analytic.line) linked to this move line
                analytic_lines = self.env['account.analytic.line'].search(
                    [('move_line_id', '=', line.id)])

                if analytic_lines:
                    # Si la nueva distribución tiene una sola cuenta, actualizamos analytic lines simple
                    if len(new_dist) == 1:
                        key = list(new_dist.keys())[0]
                        if ',' not in key and key.isdigit():
                            analytic_lines.write({'account_id': int(key)})

        # B) Cascada Inversa (Reverse Propagation)

        # 1. Compras (purchase_line_id)
        if 'purchase.order.line' not in skip_models:
            purchase_lines = lines.mapped('purchase_line_id')
            if purchase_lines:
                # Log para confirmar hallazgo
                # msg = _("Reclasificación iniciada desde Factura: Se encontraron líneas de compra relacionadas.")
                # self.env.user.notify_info(msg)
                self._reclassify_purchase_lines(
                    purchase_lines, skip_models=skip_models)

        # 2. Gastos (expense_id)
        if 'hr.expense' not in skip_models and 'expense_id' in lines._fields:
            expenses = lines.mapped('expense_id')
            if expenses:
                self._reclassify_expenses(expenses, skip_models=skip_models)

        # 3. Stock?
        # Typically stock doesn't link TO account line directly in a way we update backward

    def _reclassify_compensation_lines(self, lines):
        """Líneas de Compensación (Attendance Regularization): Project y Task"""
        vals = {}
        if self.project_id:
            vals['project_id'] = self.project_id.id
        if self.task_id:
            vals['task_id'] = self.task_id.id

        if not vals:
            # Si no hay cambios de proyecto/tarea, tal vez solo sea analitica?
            # Compensaciones no tienen analitica directa, pero sus timesheets si.
            pass

        # 1. Propagar a Timesheets vinculados (Heurística)
        if vals or self.analytic_distribution:
            for line in lines:
                if not line.employee_id or not line.date:
                    continue

                # Buscar timesheets coincidentes
                domain = [
                    ('employee_id', '=', line.employee_id.id),
                    ('date', '=', line.date),
                ]
                # Filter by current project/task to match the line being moved
                if line.project_id:
                    domain.append(('project_id', '=', line.project_id.id))
                if line.task_id:
                    domain.append(('task_id', '=', line.task_id.id))

                timesheets = self.env['account.analytic.line'].search(domain)

                if timesheets:
                    ts_vals = vals.copy()

                    # Update analytic account on timesheets if distribution changed
                    if self.analytic_distribution:
                        first_dist = self.analytic_distribution
                        if first_dist:
                            for key in first_dist.keys():
                                if ',' not in key and key.isdigit():
                                    ts_vals['account_id'] = int(key)
                                    break

                    if ts_vals:
                        timesheets.write(ts_vals)

        # 2. Actualizar las líneas de compensación
        if vals:
            lines.write(vals)

        # Sincronizar Cabecera (Compensation Request)
        unique_reqs = lines.mapped('compensation_id')
        for req in unique_reqs:
            all_lines = req.compensation_line_ids
            if all_lines:
                projects = all_lines.mapped('project_id')
                # Compensation Request doesn't have 'task_id' on header typically, just 'service' (project)
                # But let's check field definition if possible. Assuming 'service' based on previous code.

                header_vals = {}
                if len(projects) == 1:
                    header_vals['service'] = projects[0].id
                elif len(projects) > 1:
                    header_vals['service'] = False

                if header_vals:
                    req.write(header_vals)

        self._log_chatter(unique_reqs)

    def _reclassify_expenses(self, expenses, skip_models=None):
        """Gastos (Líneas): Project, Task y Analítica"""
        skip_models = skip_models or []
        skip_models.append('hr.expense')

        # A) Actualizar Project y Task
        vals = {}
        if self.project_id:
            vals['project_id'] = self.project_id.id
        if self.task_id:
            vals['task_id'] = self.task_id.id

        if vals:
            expenses.sudo().write(vals)

        # B) Actualizar Analítica
        if self.analytic_distribution:
            for expense in expenses:
                current_dist = dict(expense.analytic_distribution or {})
                new_dist = self._compute_new_distribution(current_dist)
                expense.sudo().write({'analytic_distribution': new_dist})

        # Log
        self._log_chatter(expenses)
        self._log_chatter(expenses.mapped('sheet_id'))

        # C) Propagar a Asientos Contables VINCULADOS
        if 'account.move.line' not in skip_models:
            sheets = expenses.mapped('sheet_id')
            moves = sheets.account_move_ids
            move_lines = moves.line_ids.filtered(
                lambda l: l.expense_id in expenses)

            if move_lines:
                self._reclassify_account_move_lines(
                    move_lines, skip_models=skip_models)

        if 'stock.move' not in skip_models:
            # Check if expenses have related stock moves (rare but possible in some flows)?
            pass
