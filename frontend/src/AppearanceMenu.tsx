import { useEffect, useRef, useState } from "react";
import { Check, Desktop, Moon, Sun } from "@phosphor-icons/react";

type Preference = "system" | "light" | "dark";
const KEY = "biopipe-studio-theme-v1";
const choices = [
  { value: "light", label: "浅色", Icon: Sun },
  { value: "dark", label: "深色", Icon: Moon },
  { value: "system", label: "跟随系统", Icon: Desktop },
] as const;
function valid(value: string | null): Preference {
  return value === "light" || value === "dark" ? value : "system";
}
function stored(): Preference {
  try {
    return valid(localStorage.getItem(KEY));
  } catch {
    return "system";
  }
}

export function AppearanceMenu() {
  const [preference, setPreference] = useState(stored);
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const system = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const theme =
        preference === "system"
          ? system.matches
            ? "dark"
            : "light"
          : preference;
      document.documentElement.dataset.theme = theme;
      document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute(
          "content",
          getComputedStyle(document.documentElement)
            .getPropertyValue("--panel")
            .trim(),
        );
    };
    apply();
    system.addEventListener("change", apply);
    return () => system.removeEventListener("change", apply);
  }, [preference]);
  useEffect(() => {
    const update = (event: StorageEvent) => {
      if (event.key === KEY || event.key === null) setPreference(stored());
    };
    window.addEventListener("storage", update);
    return () => window.removeEventListener("storage", update);
  }, []);
  useEffect(() => {
    if (open)
      menu.current
        ?.querySelector<HTMLButtonElement>('[aria-checked="true"]')
        ?.focus();
  }, [open]);
  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };
  const Icon = choices.find((choice) => choice.value === preference)!.Icon;
  return (
    <div
      className="appearance-menu"
      onKeyDown={(event) => {
        if (open) event.stopPropagation();
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          close();
        }
        if (event.key === "Tab") setOpen(false);
      }}
    >
      <button
        ref={trigger}
        className="icon-button appearance-trigger"
        aria-label="外观主题"
        title="外观主题"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <Icon size={19} />
      </button>
      {open && (
        <>
          <button
            className="menu-scrim"
            aria-label="关闭外观菜单"
            tabIndex={-1}
            onClick={close}
          />
          <div
            ref={menu}
            className="dropdown appearance-dropdown"
            role="menu"
            aria-label="外观主题"
            onKeyDown={(event) => {
              const buttons = Array.from(
                event.currentTarget.querySelectorAll<HTMLButtonElement>(
                  '[role="menuitemradio"]',
                ),
              );
              const index = buttons.indexOf(
                document.activeElement as HTMLButtonElement,
              );
              const next =
                event.key === "ArrowDown"
                  ? (index + 1) % buttons.length
                  : event.key === "ArrowUp"
                    ? (index - 1 + buttons.length) % buttons.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? buttons.length - 1
                        : -1;
              if (next >= 0) {
                event.preventDefault();
                buttons[next]?.focus();
              }
            }}
          >
            <div className="menu-caption">外观</div>
            {choices.map(({ value, label, Icon }) => (
              <button
                key={value}
                role="menuitemradio"
                aria-checked={preference === value}
                tabIndex={preference === value ? 0 : -1}
                onClick={() => {
                  setPreference(value);
                  try {
                    localStorage.setItem(KEY, value);
                  } catch {
                    /* The theme still works without persistent storage. */
                  }
                  close();
                }}
              >
                <Icon size={18} />
                <span>{label}</span>
                {preference === value && <Check size={15} weight="bold" />}
              </button>
            ))}
            <p className="appearance-note">主题偏好保存在此浏览器</p>
          </div>
        </>
      )}
    </div>
  );
}
