{
  "design_personality": "Swiss-minimal database dashboard with soft cream paper backdrop, crisp black typography, and refined cards. Calm, trustworthy, production-grade.",
  "brand_attributes": ["trustworthy", "precise", "calm", "elegant", "efficient"],
  "color_system": {
    "notes": "User requested Inter font, cream background and black text. Avoid saturated gradients. Keep reading surfaces solid.",
    "hex": {
      "background": "#F8F5EE",
      "foreground": "#0F0F0F",
      "card": "#FFFFFF",
      "muted": "#EDE9DD",
      "border": "#E6E1D5",
      "accent": "#1C5D5E",
      "accent-2": "#7FA39C",
      "success": "#1F7A55",
      "warning": "#B98A1C",
      "danger": "#B73E3E",
      "info": "#2F6CA6"
    },
    "css_custom_properties": ":root{--bg:#F8F5EE;--fg:#0F0F0F;--card:#FFFFFF;--muted:#EDE9DD;--border:#E6E1D5;--accent:#1C5D5E;--accent-2:#7FA39C;--success:#1F7A55;--warning:#B98A1C;--danger:#B73E3E;--info:#2F6CA6;--ring:rgba(28,93,94,0.25);--radius-sm:6px;--radius-md:10px;--radius-lg:14px;--shadow-xs:0 1px 0 rgba(15,15,15,0.03);--shadow-sm:0 1px 2px rgba(15,15,15,0.06);--shadow-md:0 3px 8px rgba(15,15,15,0.08);--shadow-lg:0 8px 24px rgba(15,15,15,0.12);--btn-radius:10px;--btn-shadow:0 2px 6px rgba(0,0,0,0.06);}",
    "status_semantics": {
      "queued": {"bg": "#F1EEE6", "fg": "#6E6652", "border": "#E3DDCF"},
      "processing": {"bg": "#E7EEF4", "fg": "#2F6CA6", "border": "#D2E0EE"},
      "completed": {"bg": "#E6F2ED", "fg": "#1F7A55", "border": "#CFE7DD"},
      "failed": {"bg": "#F7EAEA", "fg": "#B73E3E", "border": "#EED3D3"}
    },
    "gradients": {
      "usage": "Optional decorative section headers only. Do not exceed 20% viewport. No gradients on tables/cards/text blocks.",
      "examples": [
        {
          "name": "Cream Mist",
          "css": "background: linear-gradient(180deg,#FAF7F0 0%, #F8F5EE 60%, #F6F1E6 100%);"
        },
        {
          "name": "Pale Sea",
          "css": "background: linear-gradient(120deg,#F8F5EE 0%, #EEF4F2 60%, #F8F5EE 100%);"
        }
      ]
    }
  },
  "typography": {
    "font_primary": "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Noto Sans, Apple Color Emoji, Segoe UI Emoji",
    "scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl tracking-tight",
      "h2": "text-base md:text-lg font-medium",
      "body": "text-base md:text-base",
      "small": "text-sm"
    },
    "weights": {"regular": 400, "medium": 500, "semibold": 600},
    "tracking_leading": {
      "tight_display": "tracking-[-0.01em] leading-[1.1]",
      "body": "leading-[1.6]"
    }
  },
  "spacing_radius_shadows": {
    "spacing": "Use 8px base: 8,12,16,24,32,48,64. Prefer 2–3x more whitespace around cards.",
    "radius": {"sm": "6px", "md": "10px", "lg": "14px"},
    "shadows": {"card": "var(--shadow-sm)", "card-hover": "var(--shadow-md)"}
  },
  "grid_layout": {
    "container": "mx-auto px-4 sm:px-6 lg:px-8 max-w-screen-2xl",
    "layout": [
      "Header: sticky top-0 backdrop-blur bg-[color:var(--bg)]/85 border-b border-[color:var(--border)]",
      "Main: grid gap-6 lg:grid-cols-3 items-start",
      "Left column (lg:col-span-2): form card",
      "Right column (lg:col-span-1): jobs summary card",
      "Jobs table: full width below form on mobile; side-by-side on desktop"
    ],
    "cards": "bg-[color:var(--card)] border border-[color:var(--border)] rounded-[var(--radius-md)] shadow-[var(--shadow-xs)] hover:shadow-[var(--shadow-md)] transition-shadow"
  },
  "micro_interactions": {
    "rules": [
      "No universal transition. Scope to color, background-color, box-shadow.",
      "Buttons: subtle scale(0.99) on active, shadow lift on hover",
      "Rows: background tint on hover, focus-visible ring with --ring",
      "Progress bars: smooth width transition"
    ],
    "tailwind_examples": {
      "button": "transition-colors duration-200 hover:bg-[color:var(--accent)]/90 active:scale-[0.99]",
      "card": "transition-shadow duration-200 hover:shadow-[var(--shadow-md)]",
      "row": "hover:bg-[rgba(0,0,0,0.015)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--ring)]"
    }
  },
  "component_path": {
    "imports": [
      {"name": "Button", "path": "./components/ui/button"},
      {"name": "Input", "path": "./components/ui/input"},
      {"name": "Textarea", "path": "./components/ui/textarea"},
      {"name": "Card, CardHeader, CardTitle, CardContent, CardFooter", "path": "./components/ui/card"},
      {"name": "Table, TableBody, TableCell, TableHead, TableHeader, TableRow", "path": "./components/ui/table"},
      {"name": "Badge", "path": "./components/ui/badge"},
      {"name": "Progress", "path": "./components/ui/progress"},
      {"name": "Tabs, TabsList, TabsTrigger, TabsContent", "path": "./components/ui/tabs"},
      {"name": "Select, SelectContent, SelectItem, SelectTrigger, SelectValue", "path": "./components/ui/select"},
      {"name": "Skeleton", "path": "./components/ui/skeleton"},
      {"name": "ScrollArea", "path": "./components/ui/scroll-area"},
      {"name": "Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter", "path": "./components/ui/dialog"},
      {"name": "Toaster", "path": "./components/ui/sonner"}
    ],
    "icons": "lucide-react"
  },
  "components": {
    "buttons": {
      "style": "Professional / Corporate",
      "variants": {
        "primary": "bg-[color:var(--accent)] text-white hover:bg-[color:var(--accent)]/90 focus-visible:ring-2 focus-visible:ring-[color:var(--ring)]",
        "secondary": "bg-white text-[color:var(--fg)] border border-[color:var(--border)] hover:bg-[rgba(0,0,0,0.03)]",
        "ghost": "bg-transparent hover:bg-[rgba(0,0,0,0.04)]"
      },
      "sizes": {"sm": "h-8 px-3", "md": "h-10 px-4", "lg": "h-12 px-6"}
    },
    "status_chip": {
      "mapping": {
        "queued": "bg-[#F1EEE6] text-[#6E6652] border border-[#E3DDCF]",
        "processing": "bg-[#E7EEF4] text-[#2F6CA6] border border-[#D2E0EE]",
        "completed": "bg-[#E6F2ED] text-[#1F7A55] border border-[#CFE7DD]",
        "failed": "bg-[#F7EAEA] text-[#B73E3E] border border-[#EED3D3]"
      },
      "class": "px-2.5 py-1 rounded-full text-xs font-medium inline-flex items-center gap-1"
    },
    "progress": {
      "class": "h-2 rounded-full bg-[color:var(--muted)] [&>div]:bg-[color:var(--accent)]",
      "label_class": "text-xs text-neutral-600"
    },
    "cards": {
      "base": "bg-[color:var(--card)] border border-[color:var(--border)] rounded-[var(--radius-md)] shadow-[var(--shadow-xs)]",
      "header_title": "text-sm font-medium text-neutral-700"
    },
    "table": {
      "wrapper": "overflow-hidden border border-[color:var(--border)] rounded-[var(--radius-md)] bg-white",
      "table": "w-full text-sm",
      "th": "text-left text-neutral-600 font-medium p-3 border-b border-[color:var(--border)] bg-[rgba(0,0,0,0.02)]",
      "td": "p-3 border-b border-[color:var(--border)] align-top",
      "row_hover": "hover:bg-[rgba(0,0,0,0.015)]",
      "sticky_header": true,
      "zebra": true
    },
    "form": {
      "layout": "grid gap-4",
      "fields": [
        {"name": "name", "component": "Input", "placeholder": "Project or voice label", "required": true},
        {"name": "text", "component": "Textarea", "placeholder": "Paste your long text (20,000+ words supported)", "rows": 12, "required": true}
      ],
      "submit": {"label": "Create TTS Job", "variant": "primary"},
      "hints": ["Show char count live", "Soft max-height with ScrollArea for huge input"]
    },
    "filters": {
      "search": "Input with left icon (Search) and clear button",
      "status": "Select with statuses; default All"
    },
    "empty_and_loading": {
      "empty_state": "Neutral icon, 'No jobs yet', CTA to create job",
      "skeleton_rows": 5
    }
  },
  "layout_structure": {
    "header": {
      "class": "sticky top-0 z-40 bg-[color:var(--bg)]/85 backdrop-blur border-b border-[color:var(--border)]",
      "content": "Logo left, minimal right actions (About)"
    },
    "hero": {
      "title": "Text to Speech Chunker",
      "subtitle": "Process very long texts, see chunk-by-chunk progress, and download MP3s.",
      "class": "py-8 md:py-12"
    }
  },
  "image_urls": [
    {
      "url": "https://images.unsplash.com/photo-1708554908456-9ee504a2f42e?crop=entropy&cs=srgb&fm=jpg&q=85",
      "category": "background-texture",
      "description": "Subtle vintage paper texture for page background (apply with low opacity overlay)"
    },
    {
      "url": "https://images.pexels.com/photos/5908374/pexels-photo-5908374.jpeg",
      "category": "card-edge-decoration",
      "description": "Soft cream grain used as tiny corner accent masks (optional)"
    }
  ],
  "iconography": {
    "library": "lucide-react",
    "icons": {"download": "Download", "clock": "Clock", "loader": "Loader2", "search": "Search", "x": "X"}
  },
  "accessibility": {
    "contrast": "AA for all text; chips maintain >=4.5:1",
    "focus": "Use outline-none focus-visible:ring-2 ring-[color:var(--ring)]",
    "reduced_motion": "Respect prefers-reduced-motion: reduce animations",
    "aria": "Status chips include aria-label with status text"
  },
  "data_testid_policy": {
    "rule": "All interactive and key informational elements MUST include data-testid.",
    "naming": "kebab-case describing role, e.g., create-job-submit-button, jobs-table-row-<id>, job-status-badge, job-download-button, job-progress-bar",
    "coverage": ["buttons", "links", "inputs", "menus", "alerts", "table-cells with critical info", "toasts"]
  },
  "libraries": {
    "install": [
      "npm i framer-motion lucide-react",
      "npm i react-virtual --save" 
    ],
    "usage_notes": "Use framer-motion for entrance/hover only; react-virtual to render long job lists efficiently. Use shadcn/ui exclusively for UI primitives."
  },
  "js_scaffolds": {
    "status_chip_component.js": "export const StatusChip = ({ status }) => {\n  const map = {\n    queued: 'bg-[#F1EEE6] text-[#6E6652] border border-[#E3DDCF]',\n    processing: 'bg-[#E7EEF4] text-[#2F6CA6] border border-[#D2E0EE]',\n    completed: 'bg-[#E6F2ED] text-[#1F7A55] border border-[#CFE7DD]',\n    failed: 'bg-[#F7EAEA] text-[#B73E3E] border border-[#EED3D3]'\n  };\n  const cls = map[status] || map.queued;\n  return <span data-testid=\"job-status-badge\" className={\`${cls} px-2.5 py-1 rounded-full text-xs font-medium\`}>{status}</span>;\n};",
    "create_job_form.js": "import { useState } from 'react';\nimport { Card, CardHeader, CardTitle, CardContent, CardFooter } from './components/ui/card';\nimport { Input } from './components/ui/input';\nimport { Textarea } from './components/ui/textarea';\nimport { Button } from './components/ui/button';\nimport { toast } from 'sonner';\n\nexport default function CreateJobForm({ onSubmit }){\n  const [name, setName] = useState('');\n  const [text, setText] = useState('');\n  const canSubmit = name.trim() && text.trim();\n  return (\n    <Card className=\"bg-white border border-[color:var(--border)] rounded-[var(--radius-md)] shadow-[var(--shadow-xs)]\">\n      <CardHeader>\n        <CardTitle className=\"text-base md:text-lg\">Create TTS Job</CardTitle>\n      </CardHeader>\n      <CardContent className=\"grid gap-4\">\n        <div className=\"grid gap-2\">\n          <label className=\"text-sm\" htmlFor=\"name\">Name</label>\n          <Input id=\"name\" data-testid=\"job-name-input\" placeholder=\"Project or voice label\" value={name} onChange={e=>setName(e.target.value)} />\n        </div>\n        <div className=\"grid gap-2\">\n          <label className=\"text-sm\" htmlFor=\"text\">Text</label>\n          <Textarea id=\"text\" data-testid=\"job-text-textarea\" placeholder=\"Paste your long text (20,000+ words supported)\" rows={12} value={text} onChange={e=>setText(e.target.value)} />\n          <div className=\"text-xs text-neutral-600\">{text.length.toLocaleString()} chars</div>\n        </div>\n      </CardContent>\n      <CardFooter>\n        <Button data-testid=\"create-job-submit-button\" disabled={!canSubmit} onClick={() => { onSubmit?.({name, text}); toast.success('Job queued'); }}>Create TTS Job</Button>\n      </CardFooter>\n    </Card>\n  );\n}",
    "jobs_table.js": "import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './components/ui/table';\nimport { Button } from './components/ui/button';\nimport { Progress } from './components/ui/progress';\nimport { Download, Loader2 } from 'lucide-react';\nimport { StatusChip } from './StatusChip';\n\nexport const JobsTable = ({ jobs, onDownload }) => {\n  if(!jobs?.length){\n    return <div data-testid=\"jobs-empty-state\" className=\"text-sm text-neutral-600 p-6 border rounded-[var(--radius-md)] bg-white\">No jobs yet</div>;\n  }\n  return (\n    <div className=\"overflow-hidden border border-[color:var(--border)] rounded-[var(--radius-md)] bg-white\">\n      <Table className=\"w-full text-sm\">\n        <TableHeader className=\"sticky top-0 bg-[rgba(0,0,0,0.02)]\">\n          <TableRow>\n            <TableHead>Job</TableHead>\n            <TableHead>Status</TableHead>\n            <TableHead>Progress</TableHead>\n            <TableHead>Updated</TableHead>\n            <TableHead className=\"text-right\">Action</TableHead>\n          </TableRow>\n        </TableHeader>\n        <TableBody>\n          {jobs.map((j)=>{\n            const isDone = j.status === 'completed';\n            return (\n              <TableRow key={j.id} data-testid=\"jobs-table-row-\" className=\"hover:bg-[rgba(0,0,0,0.015)]\">\n                <TableCell data-testid=\"job-name-cell\">{j.name}</TableCell>\n                <TableCell><StatusChip status={j.status} /></TableCell>\n                <TableCell>\n                  <div className=\"flex items-center gap-3\">\n                    <div className=\"min-w-[140px] max-w-[240px] w-full\"><Progress data-testid=\"job-progress-bar\" value={j.progress || 0} /></div>\n                    <div className=\"text-xs text-neutral-600\">{j.chunkText || ''}</div>\n                  </div>\n                </TableCell>\n                <TableCell className=\"text-neutral-600\">{new Date(j.updatedAt).toLocaleString()}</TableCell>\n                <TableCell className=\"text-right\">\n                  <Button data-testid=\"job-download-button\" size=\"sm\" variant=\"secondary\" disabled={!isDone} onClick={() => onDownload?.(j)}>\n                    {isDone ? <Download className=\"w-4 h-4 mr-1\"/> : <Loader2 className=\"w-4 h-4 mr-1 animate-spin\"/>}\n                    {isDone ? 'Download' : 'Processing'}\n                  </Button>\n                </TableCell>\n              </TableRow>\n            );\n          })}\n        </TableBody>\n      </Table>\n    </div>\n  );\n};",
    "progress_copy_examples": [
      "Processing chunk 3/5",
      "Uploading audio…",
      "Merging chunks…",
      "Finalizing MP3"
    ],
    "polling_hook.js": "import { useEffect } from 'react';\nexport function usePolling(fetcher, interval=2000){\n  useEffect(()=>{\n    let t = setInterval(()=>{ fetcher?.(); }, interval);\n    return ()=> clearInterval(t);\n  },[fetcher, interval]);\n}",
    "page_layout.js": "import CreateJobForm from './CreateJobForm';\nimport { JobsTable } from './JobsTable';\nimport { Toaster } from './components/ui/sonner';\n\nexport default function Page({ jobs, onCreate, onDownload }){\n  return (\n    <div className=\"min-h-screen bg-[color:var(--bg)] text-[color:var(--fg)]\">\n      <header className=\"sticky top-0 z-40 bg-[color:var(--bg)]/85 backdrop-blur border-b border-[color:var(--border)]\">\n        <div className=\"mx-auto px-4 sm:px-6 lg:px-8 max-w-screen-2xl h-14 flex items-center justify-between\">\n          <div className=\"font-medium\">TTS Chunker</div>\n        </div>\n      </header>\n      <main className=\"mx-auto px-4 sm:px-6 lg:px-8 max-w-screen-2xl py-6 grid gap-6 lg:grid-cols-3\">\n        <section className=\"lg:col-span-2\"><CreateJobForm onSubmit={onCreate}/></section>\n        <aside className=\"lg:col-span-1\">\n          <div className=\"bg-white border rounded-[var(--radius-md)] p-4\">\n            <div className=\"text-sm text-neutral-700\">Jobs Summary</div>\n            {/* Add small stats here */}\n          </div>\n        </aside>\n        <section className=\"lg:col-span-3\">\n          <JobsTable jobs={jobs} onDownload={onDownload} />\n        </section>\n      </main>\n      <Toaster />\n    </div>\n  );\n}"
  },
  "testing": {
    "notes": "Ensure every button, input, progress bar, badge, row includes data-testid. Prefer role-based kebab-case names.",
    "examples": [
      "create-job-submit-button",
      "job-name-input",
      "job-text-textarea",
      "jobs-table-row-<id>",
      "job-status-badge",
      "job-download-button",
      "job-progress-bar"
    ]
  },
  "instructions_to_main_agent": [
    "Set Inter in index.css and inject color tokens into :root from color_system.css_custom_properties",
    "Apply background texture image with low opacity (2-4%) on body via after pseudo-element; never under text blocks directly if it harms readability",
    "Use shadcn/ui components only; do not use native HTML dropdowns, toasts, calendars",
    "Respect Gradient Restriction Rule; keep gradients limited to headers only if used",
    "Implement polling with usePolling hook to refresh job statuses",
    "Show chunk copy next to progress bar (e.g., 'Processing chunk 3/5')",
    "Enable sticky table header and zebra rows",
    "Use Sonner Toaster for success/error toasts at job create/complete/fail",
    "On small screens stack form then table; on large screens show 2-col layout"
  ],
  "web_inspirations": {
    "dribbble_tags": [
      "https://dribbble.com/tags/modern-dashboard",
      "https://dribbble.com/tags/dashboard-ui",
      "https://dribbble.com/tags/dashboard-design"
    ],
    "observations": [
      "Pill status chips with soft tints",
      "Thin progress bars inside table rows",
      "Cream minimal palettes with card tables"
    ]
  }
}


<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>"}],