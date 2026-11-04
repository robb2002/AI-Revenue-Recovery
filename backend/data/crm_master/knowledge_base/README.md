# Knowledge base for the blocker feature (files only)

These documents are prepared ahead of the event. They are **not** inserted into any database and **not** embedded. Chunking, embedding, and storage are done during development.

## Two kinds of document

| Prefix | Count | Origin | Label |
|---|---|---|---|
| `KB-OFF-xx` | 10 | Short verbatim excerpts from official public Pearson pages, with a source URL, collection date, and a summary in our own words | PUBLIC_VERIFIED |
| `KB-xxx-xx` | 11 | Written for the demo. Process guides, checklists, and templates | Illustrative document, SYNTHETIC |

Synthetic documents contain no real prices, no certification claims, no response-time figures, and no customer or competitor facts. Where a real organisation would hold such a figure, the document says the figure is not stated.

## File layout (chunk-friendly)
- Front matter: `doc_id`, `title`, `version`, `doc_type`, `label`, owner or source URLs, dates, `blocker_categories`.
- Each `##` heading is one natural chunk.
- Every `## Not covered by this document` section lists what the document does not say. This is what makes an `insufficient_evidence` or `partially_answered` response honest.

## Index

| doc_id | Title | Blocker categories |
|---|---|---|
| KB-OFF-01 | LMS Integration and Sign-On for Higher Education Courseware | Integration |
| KB-OFF-02 | Grade Sync Between MyLab and an LMS Gradebook | Integration, Product functionality |
| KB-OFF-03 | LTI 1.3 Integration for English Language Learning Platforms | Integration |
| KB-OFF-04 | Pearson Security Controls Overview | Security |
| KB-OFF-05 | Data Transfers and Hosting Locations | Security, Legal |
| KB-OFF-06 | Student Data and Privacy Notices | Security, Legal |
| KB-OFF-07 | Accessibility Statements for Courseware and eTextbooks | Product functionality, Procurement |
| KB-OFF-08 | Exam Delivery, Identity Checks and Accommodations (Pearson VUE) | Security, Product functionality |
| KB-OFF-09 | Higher Education Products: Pearson+, MyLab, Mastering, Revel | Product functionality |
| KB-OFF-10 | Assessment, English Language, Workforce and Virtual Learning Offers | Product functionality |
| KB-PRC-01 | Pricing and Discount Policy | Pricing |
| KB-PRD-02 | Product Fit Checklist | Product functionality |
| KB-SEC-01 | Security Questionnaire Response Pack | Security |
| KB-INT-01 | LMS Integration Planning Guide | Integration |
| KB-PRO-01 | Procurement Documentation Checklist | Procurement |
| KB-LGL-01 | Contract Terms Review Guide | Legal |
| KB-BUD-01 | Business Case Template | Budget approval |
| KB-STK-01 | Stakeholder Mapping Template | Stakeholder approval |
| KB-IMP-01 | Implementation Planning Template | Implementation timeline |
| KB-SUP-01 | Support and Service Levels Overview | Implementation timeline, Product functionality |
| KB-CMP-01 | Competitive Positioning Guide (Category Level) | Product functionality, Pricing |

The nine document IDs already referenced by `crm_master` blocker rows (KB-PRC-01, KB-PRD-02, KB-SEC-01, KB-INT-01, KB-PRO-01, KB-LGL-01, KB-BUD-01, KB-STK-01, KB-IMP-01) all exist here.

## Planted demo questions (design intent, to be validated during development)

| Question a customer might ask | Expected answer status | Where the evidence is |
|---|---|---|
| Does Pearson's LMS integration work with Brightspace (D2L)? | answered | KB-OFF-01 |
| Can grades go from MyLab back into our LMS gradebook? | answered (yes, one-way) | KB-OFF-02 |
| Will grades flow from our LMS into MyLab as well? | answered (documented as one-way; reverse not described) | KB-OFF-02 |
| Which LMS platforms does the English language platform support? | answered (four listed; differs from higher-ed list) | KB-OFF-03, KB-OFF-01 |
| Where will our student data be hosted? | partially_answered (varies by product; one product example) | KB-OFF-05 |
| Can we use SAML or OpenID Connect single sign-on? | partially_answered (sign-on through the LMS is stated; direct SAML/OIDC is not) | KB-OFF-01, KB-INT-01 |
| Is the product SOC 2 or ISO 27001 certified? | partially_answered (controls "support compliance"; no per-product statement) | KB-OFF-04, KB-SEC-01 |
| Is the courseware accessible, and can we get a VPAT? | answered | KB-OFF-07 |
| How do you confirm exam candidate identity? | answered | KB-OFF-08 |
| What is the discount for 5,000 learners over three years? | insufficient_evidence (route to Revenue Operations) | KB-PRC-01 |
| What is the guaranteed response time for a critical incident? | insufficient_evidence | KB-SUP-01 |
| Does it integrate with a platform that appears in no document? | insufficient_evidence | none |

## Quote verification
`../verify_kb_quotes.py` fetches each cited page once (robots.txt respected) and checks that every quoted excerpt in `KB-OFF-*.md` appears verbatim in the page text. The result is written to `_quote_verification.json`.

## Cautions
- Pages change. Re-run the verifier before the event and again before any demo.
- Pearson pages carry a rights notice that reserves text and data mining and AI training rights. This set therefore keeps official content to short attributed excerpts plus our own summaries, and does not copy whole pages. Confirm this approach is acceptable to your organisation before sharing the demo outside the team.
- Summaries and "illustrative guidance" are our wording, not Pearson's.
- Version numbers, owners, and dates in synthetic documents are invented for the demo.
