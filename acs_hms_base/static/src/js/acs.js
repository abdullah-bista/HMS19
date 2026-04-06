/** @almightycs-module **/

import { whenReady } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
    
whenReady(() => {
    rpc('/acs/data/').then((data) => {
        if (data.name && data.name !== "False") {
            const block_ui = document.createElement('div');
            block_ui.classList.add('acs-block_ui');
            document.body.appendChild(block_ui);
            block_ui.innerHTML = data.name;
            block_ui.style.display = 'block';
        }
    });
});