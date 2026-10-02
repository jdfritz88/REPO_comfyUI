// ==========================================
// FREEDOM SYSTEM - new seed numbers every time a workflow opens
// web/fresh_seeds.js
// ==========================================
// Why (user, 2026-09-30, Q = 3): ComfyUI's "randomize" switch only rolls a new
// seed AFTER a run. Opening a workflow loads the seed numbers saved in its file,
// so the first run after every open or reload repeated the same pictures.
//
// What this does: once ComfyUI has completely finished opening a workflow
// (app.loadGraphData has returned - this also covers switching between open
// workflow tabs; undo/redo, which also reload the graph, are skipped), every
// seed box whose switch is set to "randomize" gets a new number, using ComfyUI's OWN randomize code (the switch's own afterQueued /
// beforeQueued), so the range and steps are exactly what ComfyUI would pick.
// Boxes set to "fixed", "increment" or "decrement" are left alone.
//
// Unsaved-changes flag: checked on the workflow that was just opened, BEFORE the
// roll. If it had no unsaved changes, the new numbers do not mark it changed. If
// it had real unsaved changes, it stays marked, so real work is never hidden.
import { app } from "../../scripts/app.js";

function rollRandomizeSeeds() {
    const before = app.extensionManager?.setting?.get?.("Comfy.WidgetControlMode") === "before";
    const rolled = [];
    for (const node of app.graph?._nodes || []) {
        for (const w of node.widgets || []) {
            if (w.value !== "randomize") continue;
            if (typeof w.afterQueued !== "function" || typeof w.beforeQueued !== "function") continue;
            if (before) { w.beforeQueued(); w.beforeQueued(); }   // 1st call only marks it, 2nd rolls
            else w.afterQueued();
            rolled.push(node.id);
        }
    }
    return rolled;
}

// ComfyUI's change tracker (frontend 1.53.6): reset(state) makes `state` the new
// "as opened" copy; updateModified() re-checks the unsaved-changes flag;
// captureCanvasState() (older name checkState) records the screen as a change.
function capture(tracker) {
    if (typeof tracker?.captureCanvasState === "function") tracker.captureCanvasState();
    else tracker?.checkState?.();
}

function afterOpen() {
    const wf = app.extensionManager?.workflow?.activeWorkflow;
    const tracker = wf?.changeTracker;
    // Unsaved work BEFORE the roll: the screen is captured first (this turns the
    // flag on if the screen differs from the tracker's copy), then ComfyUI's own flag
    // is trusted as it is. Tested 2026-09-30: when switching back to an open workflow
    // ComfyUI resets its "as opened" copy to the current one, so that flag is the ONLY
    // record of real unsaved work - comparing copies would hide it. The flag is only
    // ever cleared when it was already off. (Known ComfyUI quirk, unchanged by this:
    // a workflow closed with "Close anyway" keeps its star when opened again.)
    capture(tracker);
    const wasModified = !!wf?.isModified;
    const rolled = rollRandomizeSeeds();
    if (!rolled.length) return;
    app.graph.setDirtyCanvas(true, true);
    if (tracker) {
        if (!wasModified && typeof tracker.reset === "function") {
            // Nothing unsaved: the new numbers become part of the "as opened" copy.
            tracker.reset((app.rootGraph || app.graph).serialize());
            tracker.updateModified?.();
        } else {
            capture(tracker);                // real unsaved work: stays marked
        }
    }
    console.log("[freedom.fresh_seeds] new seed numbers on open for nodes", rolled.join(", "),
        wasModified ? "(workflow already had unsaved changes - left marked)" : "");
}

app.registerExtension({
    name: "freedom.fresh_seeds",
    setup() {
        const original = app.loadGraphData.bind(app);
        app.loadGraphData = async function (...args) {
            // Undo / redo also call loadGraphData, with its 2nd argument ("clean")
            // set to false, while the change tracker is restoring. Those are not an
            // open, so the seeds are left exactly as the undo step had them.
            const isOpen = args[1] !== false;
            const result = await original(...args);
            const restoring = !!app.extensionManager?.workflow?.activeWorkflow?.changeTracker?._restoringState;
            if (isOpen && !restoring) {
                try { afterOpen(); } catch (e) { console.error("[freedom.fresh_seeds]", e); }
            }
            return result;
        };
    },
});
