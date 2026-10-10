import type { ComponentProps } from "react"
import { Group, Panel, Separator } from "react-resizable-panels"

import { cn } from "@/lib/utils"

function ResizableGroup({ className, ...props }: ComponentProps<typeof Group>) {
  return <Group className={cn("h-full min-w-0", className)} {...props} />
}

function ResizeHandle({ className, ...props }: ComponentProps<typeof Separator>) {
  return (
    <Separator
      className={cn(
        "flex w-1.5 touch-none items-center justify-center bg-border/50 outline-none hover:bg-primary/20 focus-visible:bg-primary/30",
        className,
      )}
      title="Drag to resize, or use the arrow keys. Double-click to reset."
      {...props}
    >
      <span className="h-8 w-0.5 rounded-full bg-muted-foreground/40" aria-hidden />
    </Separator>
  )
}

export { ResizableGroup, Panel as ResizablePanel, ResizeHandle }
