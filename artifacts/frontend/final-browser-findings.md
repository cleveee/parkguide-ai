# Remaining browser finding

Actual final UI on localhost. At 1280px, open Inspector and a citation EvidenceDialog. Change the browser viewport to375px while evidence remains open; a new responsive Inspector Sheet mounts behind the evidence. Return to1280px and press Escape on the visible evidence dialog. First Escape closes Inspector state but leaves evidence open; only the second Escape closes evidence. This is a modal-stack problem introduced by mounting the responsive sheet during another dialog.

Keep just one active modal layer: prevent the responsive Inspector Sheet (and mobile Menu where relevant) from opening underneath evidence, HowItWorks or conversation-confirm dialogs. Preserve the desktop inspector state and inspect actions, park resets and source evidence. Do not clear normal chat on viewport changes. Root will reproduce this scenario again after your fix.

The initial apparent Inspect-click failure afterward was a below-fold button in the conversation; pressing Enter successfully opened it, and body pointer-events wasauto. Do not treat that as a separate state defect.

Confirmed current web UI: real first and second source-reviewed answers, genuine two-message follow-up history, third absent-information refusal with four-message history and no sources, three recognized local refusals with zero events; corpus/source browser and cancellation remain to finish. Core/API are reviewed and stable.
