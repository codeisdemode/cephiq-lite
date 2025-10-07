&nbsp; 1. Files Requiring Changes



&nbsp; Core Code (3 files)



&nbsp; - cephiq\_lite/tags.py - TagKind enum, prompt builder, get\_flow\_tags()

&nbsp; - tag\_contracts.py - All flow tag definitions

&nbsp; - cephiq\_lite/envelope.py - Documentation references



&nbsp; Tests (3 files)



&nbsp; - tests/test\_tag\_manager\_integration.py - test\_flow\_tags() function

&nbsp; - tests/test\_agent\_with\_tags.py (if it uses flow tags)

&nbsp; - tests/test\_chat\_with\_tags.py (if it uses flow tags)



&nbsp; Documentation (5 files)



&nbsp; - docs/PRD.md - Architecture diagrams and tag examples

&nbsp; - docs/ARCHITECTURE\_PLAN.md - Tag system design

&nbsp; - docs/FLOWS\_ANALYSIS.md - Entire document about flows

&nbsp; - docs/tag-as-contract.md - Flow tag examples

&nbsp; - docs/openai.md - May reference flows



&nbsp; External (1 directory)



&nbsp; - flows/ directory - Contains actual workflow JSON/Python files (separate concern)



&nbsp; ---

&nbsp; 2. Current FLOW Tag Usage



&nbsp; In TagKind Enum (tags.py:20)



&nbsp; class TagKind(str, Enum):

&nbsp;     COMPANY = "company"

&nbsp;     FUNCTION = "function"

&nbsp;     ROLE = "role"

&nbsp;     FLOW = "flow"          # ← Used for tool usage guidelines

&nbsp;     TOOL = "tool"

&nbsp;     GUARDRAIL = "guardrail"



&nbsp; In Prompt Builder (tags.py:212-214)



&nbsp; if TagKind.FLOW.value in sections:

&nbsp;     prompt\_parts.append("\\n=== FLOW CONTEXT ===")

&nbsp;     prompt\_parts.extend(sections\[TagKind.FLOW.value])



&nbsp; In Tag Resolution (tags.py:266-282)



&nbsp; def get\_flow\_tags(self, intent: str) -> List\[Tag]:

&nbsp;     """Get flow tags matching an intent"""

&nbsp;     flow\_tags = \[]

&nbsp;     for tag in self.tags.values():

&nbsp;         if tag.kind == TagKind.FLOW and tag.tag.startswith(f"flow\_{intent}"):

&nbsp;             flow\_tags.append(tag)

&nbsp;     return flow\_tags



&nbsp; In Tag Contracts (tag\_contracts.py:136-251)



&nbsp; - flow\_file\_management - File operation guidelines

&nbsp; - flow\_code\_analysis - Code review approach

&nbsp; - flow\_documentation - Documentation standards



&nbsp; ---

&nbsp; 3. Proposed New Structure



&nbsp; Option A: GUIDANCE



&nbsp; class TagKind(str, Enum):

&nbsp;     COMPANY = "company"

&nbsp;     FUNCTION = "function"

&nbsp;     ROLE = "role"

&nbsp;     GUIDANCE = "guidance"      # ← Tool usage guidelines

&nbsp;     WORKFLOW = "workflow"      # ← Multi-step processes (future)

&nbsp;     TOOL = "tool"

&nbsp;     GUARDRAIL = "guardrail"



&nbsp; Naming:

&nbsp; - guidance\_file\_operations

&nbsp; - guidance\_code\_analysis

&nbsp; - guidance\_documentation



&nbsp; Prompt Section: === GUIDANCE CONTEXT ===



&nbsp; ---

&nbsp; Option B: BEST\_PRACTICES



&nbsp; class TagKind(str, Enum):

&nbsp;     COMPANY = "company"

&nbsp;     FUNCTION = "function"

&nbsp;     ROLE = "role"

&nbsp;     BEST\_PRACTICES = "best\_practices"  # ← Tool usage guidelines

&nbsp;     WORKFLOW = "workflow"               # ← Multi-step processes (future)

&nbsp;     TOOL = "tool"

&nbsp;     GUARDRAIL = "guardrail"



&nbsp; Naming:

&nbsp; - best\_practices\_file\_operations

&nbsp; - best\_practices\_code\_analysis

&nbsp; - best\_practices\_documentation



&nbsp; Prompt Section: === BEST PRACTICES ===



&nbsp; ---

&nbsp; Option C: APPROACH (Recommended)



&nbsp; class TagKind(str, Enum):

&nbsp;     COMPANY = "company"

&nbsp;     FUNCTION = "function"

&nbsp;     ROLE = "role"

&nbsp;     APPROACH = "approach"      # ← Tool usage guidelines \& methodologies

&nbsp;     WORKFLOW = "workflow"      # ← Multi-step processes (future)

&nbsp;     TOOL = "tool"

&nbsp;     GUARDRAIL = "guardrail"



&nbsp; Naming:

&nbsp; - approach\_file\_operations

&nbsp; - approach\_code\_analysis

&nbsp; - approach\_documentation



&nbsp; Prompt Section: === APPROACH CONTEXT ===



&nbsp; Why "APPROACH":

&nbsp; - ✅ Short and clear

&nbsp; - ✅ Implies methodology without prescribing exact steps

&nbsp; - ✅ Fits with current content (guidelines on "how to approach" tasks)

&nbsp; - ✅ Distinct from "WORKFLOW" (future multi-step orchestration)



&nbsp; ---

&nbsp; 4. Required Code Changes



&nbsp; Change 1: TagKind Enum (tags.py:15-22)



&nbsp; # OLD

&nbsp; class TagKind(str, Enum):

&nbsp;     FLOW = "flow"



&nbsp; # NEW

&nbsp; class TagKind(str, Enum):

&nbsp;     APPROACH = "approach"

&nbsp;     WORKFLOW = "workflow"  # Reserved for future true workflows



&nbsp; ---

&nbsp; Change 2: Prompt Builder (tags.py:212-214)



&nbsp; # OLD

&nbsp; if TagKind.FLOW.value in sections:

&nbsp;     prompt\_parts.append("\\n=== FLOW CONTEXT ===")

&nbsp;     prompt\_parts.extend(sections\[TagKind.FLOW.value])



&nbsp; # NEW

&nbsp; if TagKind.APPROACH.value in sections:

&nbsp;     prompt\_parts.append("\\n=== APPROACH CONTEXT ===")

&nbsp;     prompt\_parts.extend(sections\[TagKind.APPROACH.value])



&nbsp; ---

&nbsp; Change 3: Tag Resolution Method (tags.py:266-282)



&nbsp; # OLD

&nbsp; def get\_flow\_tags(self, intent: str) -> List\[Tag]:



&nbsp; # NEW (rename and update logic)

&nbsp; def get\_approach\_tags(self, intent: str = "") -> List\[Tag]:

&nbsp;     """Get approach tags for tool usage guidelines"""

&nbsp;     approach\_tags = \[]

&nbsp;     for tag in self.tags.values():

&nbsp;         if tag.kind == TagKind.APPROACH:

&nbsp;             if not intent or tag.tag.endswith(f"\_{intent}"):

&nbsp;                 approach\_tags.append(tag)

&nbsp;     return approach\_tags



&nbsp; ---

&nbsp; Change 4: Tag Contract Definitions (tag\_contracts.py:136-251)



&nbsp; # OLD

&nbsp; def create\_flow\_tags():

&nbsp;     return \[

&nbsp;         Tag(

&nbsp;             tag="flow\_file\_management",

&nbsp;             kind=TagKind.FLOW,

&nbsp;             ...



&nbsp; # NEW

&nbsp; def create\_approach\_tags():

&nbsp;     return \[

&nbsp;         Tag(

&nbsp;             tag="approach\_file\_operations",

&nbsp;             kind=TagKind.APPROACH,

&nbsp;             ...



&nbsp; ---

&nbsp; Change 5: Test Updates (tests/test\_tag\_manager\_integration.py:214-262)



&nbsp; # OLD

&nbsp; def test\_flow\_tags():

&nbsp;     checkout\_flow = Tag(

&nbsp;         tag="flow\_checkout",

&nbsp;         kind=TagKind.FLOW,

&nbsp;     ...

&nbsp;     flow\_tags = tag\_manager.get\_flow\_tags("checkout")



&nbsp; # NEW

&nbsp; def test\_approach\_tags():

&nbsp;     checkout\_approach = Tag(

&nbsp;         tag="approach\_checkout\_operations",

&nbsp;         kind=TagKind.APPROACH,

&nbsp;     ...

&nbsp;     approach\_tags = tag\_manager.get\_approach\_tags("checkout")



&nbsp; ---

&nbsp; 5. Migration Strategy



&nbsp; Phase 1: Add New, Keep Old (Backward Compatible)



&nbsp; 1. Add TagKind.APPROACH to enum (keep FLOW)

&nbsp; 2. Add TagKind.WORKFLOW to enum (for future)

&nbsp; 3. Update prompt builder to handle both FLOW and APPROACH

&nbsp; 4. Add new approach tags alongside existing flow tags



&nbsp; Timeline: 1-2 hoursRisk: Low (no breaking changes)



&nbsp; ---

&nbsp; Phase 2: Migrate Tags



&nbsp; 1. Rename all flow\_\* tags to approach\_\*

&nbsp; 2. Update tag\_contracts.py function names

&nbsp; 3. Update test references

&nbsp; 4. Update documentation



&nbsp; Timeline: 2-3 hoursRisk: Medium (breaks existing configs if users created custom flow tags)



&nbsp; ---

&nbsp; Phase 3: Deprecate FLOW



&nbsp; 1. Mark TagKind.FLOW as deprecated

&nbsp; 2. Add warning when FLOW tags are used

&nbsp; 3. Update all documentation to use APPROACH



&nbsp; Timeline: 1 hourRisk: Low (migration path provided)



&nbsp; ---

&nbsp; Phase 4: Remove FLOW (Breaking Change)



&nbsp; 1. Remove TagKind.FLOW from enum

&nbsp; 2. Remove backward compatibility code

&nbsp; 3. Update to v2.0.0



&nbsp; Timeline: 1 hourRisk: High (breaking change for any external users)



&nbsp; ---

&nbsp; 6. Impact Summary



&nbsp; Files to Modify



&nbsp; - Core: 2 files (tags.py, tag\_contracts.py)

&nbsp; - Tests: 1 file (test\_tag\_manager\_integration.py)

&nbsp; - Docs: 5 files (PRD.md, ARCHITECTURE\_PLAN.md, FLOWS\_ANALYSIS.md, tag-as-contract.md, openai.md)



&nbsp; Breaking Changes



&nbsp; - TagKind.FLOW → TagKind.APPROACH

&nbsp; - get\_flow\_tags() → get\_approach\_tags()

&nbsp; - create\_flow\_tags() → create\_approach\_tags()

&nbsp; - Tag names: flow\_\* → approach\_\*

&nbsp; - Prompt section: FLOW CONTEXT → APPROACH CONTEXT



&nbsp; Effort Estimate



&nbsp; - Code changes: 3-4 hours

&nbsp; - Test updates: 1-2 hours

&nbsp; - Documentation: 2-3 hours

&nbsp; - Total: 6-9 hours



&nbsp; Risk Assessment



&nbsp; - Low risk: No external API changes (internal framework only)

&nbsp; - Medium risk: Breaking change for users who created custom flow tags

&nbsp; - Mitigation: Provide migration guide and backward compatibility period



&nbsp; ---

&nbsp; 7. Recommendation



&nbsp; Recommended Approach: APPROACH (Option C)



&nbsp; Migration Path:

&nbsp; 1. Phase 1 (Now): Add APPROACH + WORKFLOW to enum, support both

&nbsp; 2. Phase 2 (v1.5): Migrate all tags, deprecate FLOW

&nbsp; 3. Phase 3 (v2.0): Remove FLOW entirely



&nbsp; Benefits:

&nbsp; - ✅ Clear semantic distinction: APPROACH = guidelines, WORKFLOW = orchestration

&nbsp; - ✅ Preserves FLOW tags temporarily for backward compatibility

&nbsp; - ✅ Opens path for true workflow implementation

&nbsp; - ✅ Minimal breaking changes with migration period



