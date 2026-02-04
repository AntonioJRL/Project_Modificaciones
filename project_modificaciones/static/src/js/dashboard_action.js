/** @odoo-module **/

/*
 * Este módulo define un servicio de JavaScript personalizado para manejar acciones
 * desde vistas HTML o Dashboards personalizados en Odoo.
 * 
 * Problema: Los campos HTML estándar en Odoo no pueden activar acciones de ventana (ir.actions.act_window)
 * con comportamiento de modal (target="new") fácilmente usando solo hrefs normales.
 * 
 * Solución: Este script escucha clics en elementos con la clase CSS "js_dashboard_action" y 
 * utiliza el servicio de acción nativo de Odoo (actionService) para ejecutar la acción deseada.
 */

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

export const dashboardActionService = {
    // El método start se ejecuta cuando Odoo inicializa este servicio
    start(env) {
        // Agregamos un "event listener" al cuerpo del documento (document.body).
        // Usamos "delegación de eventos": escuchamos todos los clics, pero solo actuamos
        // si el elemento clickeado (o su padre) tiene la clase 'js_dashboard_action'.
        document.body.addEventListener('click', async (ev) => {
            const link = ev.target.closest('.js_dashboard_action');

            // Si el clic no fue en un elemento nuestro, no hacemos nada.
            if (!link) return;

            // Prevenimos la navegación predeterminada del navegador (para que no recargue la página o cambie la URL hash)
            ev.preventDefault();
            ev.stopPropagation();

            // Obtenemos el servicio de acción de Odoo del entorno (env)
            const actionService = env.services.action;

            // Extraemos los datos definidos en los atributos HTML (data-*) del enlace
            // data-xml-id: ID externo de la acción a ejecutar (ej. 'modulo.accion_xml')
            const xmlId = link.dataset.xmlId;
            // data-model: Modelo del registro a abrir directamente (ej. 'project.task')
            const resModel = link.dataset.model;
            // data-id: ID numérico del registro a abrir
            const resId = parseInt(link.dataset.id);
            // data-active-id: ID para pasar al contexto como 'active_id' (importante para filtrados o valores por defecto)
            const activeId = parseInt(link.dataset.activeId);

            if (xmlId) {
                // CASO 1: Ejecutar una Acción por su XML ID
                // Esto es útil para abrir listas, wizards o vistas específicas configuradas en XML.

                // Construimos el contexto. Si hay un activeId, lo pasamos como active_id, active_ids y active_model.
                // Esto es crucial porque muchas acciones en Odoo dependen de 'active_id' para saber sobre qué registro filtrar.
                const context = {
                    ...activeId ? {
                        active_id: activeId,
                        active_ids: [activeId],
                        // Asumimos 'sale.order.line' por defecto si no se especifica, o se podría pasar otro data-attribute.
                        // Para este caso específico del dashboard, ayuda a que las vistas sepan el contexto.
                        active_model: 'sale.order.line'
                    } : {}
                };

                // Ejecutamos la acción con additionalContext
                await actionService.doAction(xmlId, {
                    additionalContext: context,
                    target: 'new' // Forzamos que se abra como modal (wizard)
                });

            } else if (resModel && resId) {
                // CASO 2: Abrir un registro específico en vista Formulario
                // Útil para enlaces directos como "Ver Avance #123"

                await actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: resModel,
                    res_id: resId,
                    views: [[false, 'form']], // Forzamos vista formulario
                    target: 'new',            // Forzamos modal
                });
            }
        });
    }
};

// Registramos el servicio en la categoría "services" de Odoo para que arranque automáticamente.
registry.category("services").add("dashboard_action_handler", dashboardActionService);
