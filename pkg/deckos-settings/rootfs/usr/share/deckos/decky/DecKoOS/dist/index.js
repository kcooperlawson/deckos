const manifest = {"name":"DecKoOS","author":"kcooperlawson","flags":[],"api_version":1,"publish":{"tags":["deckos","profiles","sound"],"description":"DecKoOS in Gaming Mode: the running game's profile, power, sound and Game Doctor.","image":""}};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const toaster = api.toaster;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

// DecKoOS in Gaming Mode's quick access menu: the running game's profile, power, sound and Game Doctor.
// Everything is read from and done by /usr/lib/deckos/decky/bridge.py (through main.py); this file only draws it.


const snapshot = callable("snapshot");
const setPower = callable("power");
const setProfile = callable("profile");
const setOutput = callable("output");
const setKind = callable("kind");
const setEq = callable("eq");
const POWER = [
    { data: "performance", label: "Performance" },
    { data: "balanced", label: "Balanced" },
    { data: "power-saver", label: "Power saver" },
];
function said(r, what) {
    if (!r.ok)
        toaster.toast({ title: "DecKoOS", body: `${what} didn't work: ${r.error}` });
}
function Icon() {
    // The DecKoOS plate: a rounded square with two screw heads
    return (window.SP_REACT.createElement("svg", { viewBox: "0 0 24 24", width: "1em", height: "1em", fill: "none", stroke: "currentColor", strokeWidth: "1.75" },
        window.SP_REACT.createElement("rect", { x: "3", y: "5", width: "18", height: "14", rx: "3" }),
        window.SP_REACT.createElement("circle", { cx: "7.5", cy: "12", r: "1.6" }),
        window.SP_REACT.createElement("circle", { cx: "16.5", cy: "12", r: "1.6" })));
}
function Content() {
    const [s, setS] = SP_REACT.useState(null);
    const load = () => snapshot().then(setS);
    SP_REACT.useEffect(() => {
        load();
    }, []);
    if (!s)
        return window.SP_REACT.createElement(DFL.PanelSection, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null, "Reading DecKoOS\u2026"));
    if (s.error)
        return window.SP_REACT.createElement(DFL.PanelSection, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null, s.error));
    const game = s.game;
    return (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
        window.SP_REACT.createElement(DFL.PanelSection, { title: game ? game.name : "No game running" }, game ? (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.DropdownItem, { label: "Power while it runs", rgOptions: [{ data: "", label: "As usual" }, ...POWER], selectedOption: s.profile.power ?? "", onChange: async (o) => {
                        said(await setProfile(game.id, "power", o.data, game.name), "Power");
                        load();
                    } })),
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.ToggleField, { label: "Do not disturb", description: "No notifications while this game runs", checked: !!s.profile.dnd, onChange: async (v) => {
                        said(await setProfile(game.id, "dnd", v ? "true" : "false", game.name), "Do not disturb");
                        load();
                    } })))) : (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.DropdownItem, { label: "Power", rgOptions: POWER, selectedOption: s.power, onChange: async (o) => {
                    said(await setPower(o.data), "Power");
                    load();
                } })))),
        window.SP_REACT.createElement(DFL.PanelSection, { title: "Sound" },
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.DropdownItem, { label: "Plays on", rgOptions: s.outputs.map((o) => ({ data: o.name, label: o.label })), selectedOption: s.outputs.find((o) => o.default)?.name, onChange: async (o) => {
                        said(await setOutput(o.data), "Changing the output");
                        load();
                    } })),
            s.kinds.map((k) => (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: k.id },
                window.SP_REACT.createElement(DFL.SliderField, { label: k.name, value: k.volume, min: 0, max: 100, step: 5, showValue: true, onChange: async (v) => said(await setKind(k.id, v), k.name) })))),
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.DropdownItem, { label: "Equalizer", rgOptions: s.eq_presets.map((p) => ({ data: p.id, label: p.name })), selectedOption: s.eq, onChange: async (o) => {
                        said(await setEq(o.data), "The equalizer");
                        load();
                    } }))),
        (s.doctor || s.problems.length > 0) && (window.SP_REACT.createElement(DFL.PanelSection, { title: "Needs a look" },
            s.doctor && window.SP_REACT.createElement(DFL.PanelSectionRow, null, s.doctor),
            s.problems.map((p) => (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: p }, p)))))));
}
var index = definePlugin(() => ({
    name: "DecKoOS",
    titleView: window.SP_REACT.createElement("div", { className: DFL.staticClasses.Title }, "DecKoOS"),
    content: window.SP_REACT.createElement(Content, null),
    icon: window.SP_REACT.createElement(Icon, null),
}));

export { index as default };
//# sourceMappingURL=index.js.map
