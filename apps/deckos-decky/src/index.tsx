// DecKoOS in Gaming Mode's quick access menu: the running game's profile, power, sound and Game Doctor.
// Everything is read from and done by /usr/lib/deckos/decky/bridge.py (through main.py); this file only draws it.
import { callable, definePlugin, toaster } from "@decky/api";
import {
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  staticClasses,
} from "@decky/ui";
import { useEffect, useState } from "react";

type Output = { name: string; label: string; default: boolean; volume: number };
type Kind = { id: string; name: string; volume: number };
type Snapshot = {
  error?: string;
  game: { id: string; name: string } | null;
  profile: { power?: string; dnd?: boolean };
  power: string;
  outputs: Output[];
  kinds: Kind[];
  eq: string;
  eq_presets: { id: string; name: string }[];
  doctor: string;
  problems: string[];
};
type Done = { ok: boolean; error?: string };

const snapshot = callable<[], Snapshot>("snapshot");
const setPower = callable<[string], Done>("power");
const setProfile = callable<[string, string, string, string], Done>("profile");
const setOutput = callable<[string], Done>("output");
const setKind = callable<[string, number], Done>("kind");
const setEq = callable<[string], Done>("eq");

const POWER = [
  { data: "performance", label: "Performance" },
  { data: "balanced", label: "Balanced" },
  { data: "power-saver", label: "Power saver" },
];

function said(r: Done, what: string) {
  if (!r.ok) toaster.toast({ title: "DecKoOS", body: `${what} didn't work: ${r.error}` });
}

function Icon() {
  // The DecKoOS plate: a rounded square with two screw heads
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="3" y="5" width="18" height="14" rx="3" />
      <circle cx="7.5" cy="12" r="1.6" />
      <circle cx="16.5" cy="12" r="1.6" />
    </svg>
  );
}

function Content() {
  const [s, setS] = useState<Snapshot | null>(null);
  const load = () => snapshot().then(setS);
  useEffect(() => {
    load();
  }, []);

  if (!s) return <PanelSection><PanelSectionRow>Reading DecKoOS…</PanelSectionRow></PanelSection>;
  if (s.error) return <PanelSection><PanelSectionRow>{s.error}</PanelSectionRow></PanelSection>;

  const game = s.game;
  return (
    <>
      <PanelSection title={game ? game.name : "No game running"}>
        {game ? (
          <>
            <PanelSectionRow>
              <DropdownItem
                label="Power while it runs"
                rgOptions={[{ data: "", label: "As usual" }, ...POWER]}
                selectedOption={s.profile.power ?? ""}
                onChange={async (o) => {
                  said(await setProfile(game.id, "power", o.data, game.name), "Power");
                  load();
                }}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Do not disturb"
                description="No notifications while this game runs"
                checked={!!s.profile.dnd}
                onChange={async (v) => {
                  said(await setProfile(game.id, "dnd", v ? "true" : "false", game.name), "Do not disturb");
                  load();
                }}
              />
            </PanelSectionRow>
          </>
        ) : (
          <PanelSectionRow>
            <DropdownItem
              label="Power"
              rgOptions={POWER}
              selectedOption={s.power}
              onChange={async (o) => {
                said(await setPower(o.data), "Power");
                load();
              }}
            />
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Sound">
        <PanelSectionRow>
          <DropdownItem
            label="Plays on"
            rgOptions={s.outputs.map((o) => ({ data: o.name, label: o.label }))}
            selectedOption={s.outputs.find((o) => o.default)?.name}
            onChange={async (o) => {
              said(await setOutput(o.data), "Changing the output");
              load();
            }}
          />
        </PanelSectionRow>
        {s.kinds.map((k) => (
          <PanelSectionRow key={k.id}>
            <SliderField
              label={k.name}
              value={k.volume}
              min={0}
              max={100}
              step={5}
              showValue
              onChange={async (v) => said(await setKind(k.id, v), k.name)}
            />
          </PanelSectionRow>
        ))}
        <PanelSectionRow>
          <DropdownItem
            label="Equalizer"
            rgOptions={s.eq_presets.map((p) => ({ data: p.id, label: p.name }))}
            selectedOption={s.eq}
            onChange={async (o) => {
              said(await setEq(o.data), "The equalizer");
              load();
            }}
          />
        </PanelSectionRow>
      </PanelSection>

      {(s.doctor || s.problems.length > 0) && (
        <PanelSection title="Needs a look">
          {s.doctor && <PanelSectionRow>{s.doctor}</PanelSectionRow>}
          {s.problems.map((p) => (
            <PanelSectionRow key={p}>{p}</PanelSectionRow>
          ))}
        </PanelSection>
      )}
    </>
  );
}

export default definePlugin(() => ({
  name: "DecKoOS",
  titleView: <div className={staticClasses.Title}>DecKoOS</div>,
  content: <Content />,
  icon: <Icon />,
}));
