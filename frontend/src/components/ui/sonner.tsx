import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon, XIcon } from "lucide-react"

// Sonner pins its close button to the toast's top-left corner (absolute, 20px,
// half outside the box). Its own hooks for changing that are `classNames.closeButton`
// and `icons.close`, used below: the button becomes a normal flex item pushed to the
// right (`order-last ml-auto`), so the toast's `align-items: center` centres it
// vertically and it can never overlap the text. `!` is needed because Sonner's
// stylesheet selector is more specific than a plain utility class. Size comes from
// --toast-close-size in index.css (44px hit area). Hover/active invert to ink/white;
// the focus ring is currentColor (ink on lime, white on red/ink), 3px, drawn inside.
const CLOSE_BUTTON =
  "!static !order-last !ml-auto !flex !size-(--toast-close-size) !shrink-0 !transform-none !items-center !justify-center !rounded-none !border-0 !bg-transparent !p-0 !text-current " +
  "hover:!bg-ink hover:!text-on-ink active:!bg-ink active:!text-on-ink " +
  "focus-visible:!bg-transparent focus-visible:!shadow-none focus-visible:!outline-[3px] focus-visible:!outline-offset-[-5px] focus-visible:!outline-current"

// closeLabel: the accessible name of the X button, in the current language.
const Toaster = ({ closeLabel, ...props }: ToasterProps & { closeLabel?: string }) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: (
          <CircleCheckIcon className="size-4" />
        ),
        info: (
          <InfoIcon className="size-4" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4" />
        ),
        error: (
          <OctagonXIcon className="size-4" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
        close: <XIcon className="size-6" strokeWidth={2.5} aria-hidden />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      toastOptions={{
        closeButtonAriaLabel: closeLabel,
        classNames: {
          toast: "cn-toast !py-2.5 !pr-2.5 [&_[data-content]]:min-w-0",
          description: "[overflow-wrap:anywhere]",
          closeButton: CLOSE_BUTTON,
          success: "!rounded-none !border-[3px] !border-ink !bg-lime !text-ink !shadow-hard-sm",
          error: "!rounded-none !border-[3px] !border-ink !bg-destructive !text-on-ink !shadow-hard-sm",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
