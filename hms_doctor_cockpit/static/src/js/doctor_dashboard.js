/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const STATE_LABELS = {
    draft: "Draft",
    confirm: "Confirmed",
    waiting: "Waiting",
    in_consultation: "In Consultation",
    pause: "Paused",
    to_invoice: "To Invoice",
    done: "Done",
    cancel: "Cancelled",
};

const STATE_BADGE_CLASS = {
    waiting: "bg-warning text-dark",
    in_consultation: "bg-success",
    pause: "bg-secondary",
    confirm: "bg-info",
    draft: "bg-light text-dark border",
    to_invoice: "bg-primary",
    done: "bg-success",
    cancel: "bg-danger",
};

export class DoctorDashboard extends Component {
    static template = "hms_doctor_cockpit.DoctorDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // this.user = useService("user");

        this.state = useState({
            physicianId: null,
            physicianName: "",
            stats: {
                todayAppts: 0,
                waitingPatients: 0,
                activeTreatments: 0,
                draftPrescriptions: 0,
                labResultsReady: 0,
            },
            todayQueue: [],
            loading: true,
            noPhysicianRecord: false,
        });

        onWillStart(() => this._loadData());
    }

    async _loadData() {
        const physicians = await this.orm.searchRead(
            "hms.physician",
            [["user_id", "=", user.userId]],
            ["id", "name"],
            { limit: 1 }
        );

        if (!physicians.length) {
            this.state.noPhysicianRecord = true;
            this.state.loading = false;
            return;
        }

        const { id: physicianId, name: physicianName } = physicians[0];
        this.state.physicianId = physicianId;
        this.state.physicianName = physicianName;

        const today = new Date().toISOString().split("T")[0];

        const [
            todayAppts,
            waitingPatients,
            activeTreatments,
            draftPrescriptions,
            labResultsReady,
            todayQueue,
        ] = await Promise.all([
            this.orm.searchCount("hms.appointment", [
                ["physician_id", "=", physicianId],
                ["appointment_date", "=", today],
                ["state", "not in", ["cancel"]],
            ]),
            this.orm.searchCount("hms.appointment", [
                ["physician_id", "=", physicianId],
                ["state", "=", "waiting"],
            ]),
            this.orm.searchCount("hms.admission", [
                ["attending_physician_id", "=", physicianId],
                ["state", "=", "in_progress"],
            ]),
            this.orm.searchCount("prescription.order", [
                ["physician_id", "=", physicianId],
                ["state", "=", "draft"],
            ]),
            this.orm.searchCount("patient.laboratory.test", [
                ["physician_id", "=", physicianId],
                ["state", "=", "done"],
            ]),
            this.orm.searchRead(
                "hms.appointment",
                [
                    ["physician_id", "=", physicianId],
                    ["appointment_date", "=", today],
                    ["state", "not in", ["cancel", "done"]],
                ],
                ["patient_id", "date", "state", "chief_complain"],
                { order: "date asc", limit: 20 }
            ),
        ]);

        Object.assign(this.state.stats, {
            todayAppts,
            waitingPatients,
            activeTreatments,
            draftPrescriptions,
            labResultsReady,
        });
        this.state.todayQueue = todayQueue;
        this.state.loading = false;
    }

    stateBadgeClass(state) {
        return STATE_BADGE_CLASS[state] || "bg-secondary";
    }

    stateLabel(state) {
        return STATE_LABELS[state] || state;
    }

    formatTime(datetimeStr) {
        if (!datetimeStr) return "—";
        const date = new Date(datetimeStr.replace(" ", "T") + "Z");
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    get todayDateString() {
        return new Date().toLocaleDateString(undefined, {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        });
    }

    openAction(xmlId) {
        this.action.doAction(xmlId);
    }

    openAppointment(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hms.appointment",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("hms_doctor_cockpit.doctor_dashboard", DoctorDashboard);
