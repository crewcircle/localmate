interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  "aria-label"?: string;
}

/**
 * Accessible on/off toggle switch matching the app's accent design tokens.
 */
export default function Toggle({ checked, onChange, ...rest }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 flex-none rounded-full transition-colors ${
        checked ? "bg-accent" : "bg-border"
      }`}
      {...rest}
    >
      <span
        className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-background shadow transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}
