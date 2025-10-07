🧭 1. Core Principle



“Tags = Prompt Building Blocks”



Instead of scattering instructions, flows, roles, or tool descriptions across code, each Tag acts as a semantic contract record.

At runtime, the orchestrator simply loads the tags relevant to the current session/user/context and injects their content into the system prompt.



🧱 2. Tag Schema (Unified)

{

&nbsp; "tag": "flow\_checkout",

&nbsp; "kind": "flow",

&nbsp; "payload": {

&nbsp;   "meta": {

&nbsp;     "name": "Checkout Flow",

&nbsp;     "description": "How to handle the checkout process"

&nbsp;   },

&nbsp;   "config": {

&nbsp;     "allowed\_tools": \["verify\_payment", "create\_order", "send\_receipt"],

&nbsp;     "assigned\_roles": \["checkout\_agent", "sales\_manager"],

&nbsp;     "assigned\_users": \["user\_123", "user\_456"],

&nbsp;     "org\_scope": "acme\_inc"

&nbsp;   },

&nbsp;   "content": "1. Verify payment.\\n2. Create order.\\n3. Send receipt to the customer."

&nbsp; }

}





Other tag kinds follow the same pattern:



company\_acme\_inc — Company branding, values, general instructions



function\_sales\_manager — Department or role definition



role\_checkout\_agent — Persona, tone, and responsibility



tool\_verify\_payment — Tool schema, usage policy, and safety notes



guardrail\_rate\_limit\_weather — Optional runtime constraints



All stored in one central tag table (e.g., PostgreSQL, Supabase, or any config service).



🧠 3. Prompt Assembly Pipeline



Step 1: User starts a session → system resolves which tags apply:



Company tags (by org)



Function tags (by assigned user/role)



Role tags (persona / authority)



Flow tags (based on intent or user function)



Tool tags (automatically based on allowed\_tools in flow/function tags)



Step 2: For each tag, orchestrator retrieves content and builds a structured system prompt:



=== COMPANY CONTEXT ===

{{ company\_acme\_inc.content }}



=== FUNCTION CONTEXT ===

{{ function\_sales\_manager.content }}



=== ROLE CONTEXT ===

{{ role\_checkout\_agent.content }}



=== FLOW CONTEXT ===

{{ flow\_checkout.content }}



=== TOOLS AVAILABLE ===

{{ tool\_verify\_payment.content }}

{{ tool\_create\_order.content }}

{{ tool\_send\_receipt.content }}





Step 3: Inject this as the system message for the model.



This gives the model:



Company personality \& goals



Functional responsibilities



Persona voice \& authority



Business process flow



Exact tool schemas \& rules



All from tags 🔥



🛡 4. Centralized RBAC / Authority



Because assigned\_users, assigned\_roles, and org\_scope live in each tag’s config, the tag system doubles as a Role-Based Access Control (RBAC) layer:



Only tags relevant to the authenticated user are loaded



Allowed tools are aggregated from function/flow/tool tags



Backend can enforce tool use against allowed\_tools at runtime



This gives you ERP-like centralized control:



Adding a new sales manager = assign user to function\_sales\_manager tag → everything else just works



Updating a flow = edit flow\_checkout tag → all prompts update automatically



Revoking tool access = remove tool from tag config → instantly enforced everywhere



🧭 5. Tag Composition Rules



You can define merge priorities to avoid conflicts:



Tag Kind	Merge Priority	Purpose

Company	Lowest	Global org rules

Function	Medium	Departmental policies

Role	Medium+	Persona and behavioral context

Flow	High	Business process instructions

Tool	Highest	Technical schemas and guardrails



This ensures a consistent, predictable prompt structure.



⚡ 6. Advantages



✅ Centralized Management

All flows, tools, functions, personas, and company settings live in one table.



✅ Live Updates

Update a tag → next prompt automatically reflects changes (no code changes).



✅ RBAC Integration

Same tag metadata controls who gets what instructions \& tools.



✅ Scalability

Works across orgs, roles, and functions without prompt spaghetti.



✅ Auditable

Tags can be versioned → you have a full history of what instructions existed at any time.



✅ Composable Prompts

Prompt = Σ(tag.contents) in structured sections. Easy to reason about.



🧪 7. Optional Dynamic Layer



For static company + function + tool tags, injection is perfect.

For ad-hoc / user-defined contracts, you can still use RAG retrieval from a vector DB (e.g., Pinecone). But that becomes supplementary, not core.



✨ 8. Summary



🏷 Tags become the single source of truth for:



Prompt content (system messages)



RBAC authority



Tool policies



Business flows



You end up with a declarative, centralized configuration system that controls both how the LLM behaves and what it’s allowed to do — exactly like ERP systems manage roles, flows, and permissions.

