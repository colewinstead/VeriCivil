import type { Metadata } from "next";
import LegalShell from "../LegalShell";
import { TERMS_EFFECTIVE_DATE } from "@/lib/billing/legal";

export const metadata: Metadata = { title: "Terms of Service" };

export default function TermsPage() {
  return (
    <LegalShell title="Terms of Service" effectiveDate={TERMS_EFFECTIVE_DATE}>
      <p>These Terms govern the Superelevation Calculator website, browser application, paid features, documentation, and related services (the <strong>Service</strong>). The Service is operated by CW Aerial Media LLC (<strong>Provider</strong>) under the VeriCivil brand. By accepting these Terms, creating a paid account, or using a paid feature, the customer agrees personally or for the organization it is authorized to bind.</p>

      <section><h2>1. Engineering aid and responsible professional</h2>
        <p>The Service is an engineering aid. It does not replace professional judgment, project-specific review, governing standards, agency approval, or the duties of the licensed professional responsible for a project.</p>
        <p><strong>The licensed professional responsible for the project must independently verify criteria, inputs, assumptions, units, stationing, coordinate systems, calculations, results, warnings, and deliverables against governing standards and project requirements before relying on or issuing any work.</strong></p>
        <p>The Service does not select the governing standard, approve design exceptions, or assume responsible charge. The customer must confirm that every selected criteria profile, revision, override, and project condition is appropriate.</p>
      </section>

      <section><h2>2. Accounts, plans, and entitlements</h2>
        <p>Free manual calculations may be used without a Superelevation Calculator account. Pro requires a named account and includes the professional workflows displayed on the plan page. Team access is available only through a separately accepted order. Accounts and named seats may not be shared.</p>
        <p>Entitlements control access to workflow features. They never change formulas, criteria, lookup tables, stationing, coordinate transforms, or calculation results. Authentication, payment, cancellation, expiration, or an entitlement outage will not recalculate saved results or silently substitute a criteria profile.</p>
      </section>

      <section><h2>3. License</h2>
        <p>Subject to these Terms and payment, Provider grants a limited, nonexclusive, nontransferable, nonsublicensable right to use the Service for the customer&apos;s internal business purposes during the paid term. Customer-created project files and deliverables remain the customer&apos;s property.</p>
        <p>Customers may not share accounts, evade entitlement controls, resell the Service, bypass security, interfere with operation, remove version or warning notices, or claim Provider approved, stamped, certified, or assumed responsible charge for customer engineering work.</p>
      </section>

      <section><h2>4. Local engineering data</h2>
        <p>Project files, project names, LandXML, engineering inputs, calculations, and PDF, CSV, and DXF exports are processed locally on the user&apos;s device. They are not uploaded to authentication, billing, or entitlement services.</p>
        <p>The customer controls local storage, access, backups, recovery, and secure transfer. Provider cannot recover files that remain only on the customer&apos;s device. A customer may voluntarily send selected material for support only through an authorized channel.</p>
      </section>

      <section><h2>5. Supported scope and standards</h2>
        <p>Supported browsers, files, geometry, criteria profiles, source revisions, and known limitations are identified in the Service or documentation. Standards may change independently. Provider will not silently replace the profile recorded in an existing project. The customer determines whether a profile or update applies to its work.</p>
        <p>The desktop edition is Coming soon and is not included unless a later order expressly includes it.</p>
      </section>

      <section><h2>6. Billing, renewal, cancellation, and refunds</h2>
        <p>Pro costs <strong>$29 USD per month</strong> and renews automatically each month until canceled. The exact charge is displayed again in Stripe Checkout before payment. Customers may cancel through the Stripe-hosted billing portal. Cancellation takes effect at the end of the current paid period, and Pro remains available through that period.</p>
        <p>Payments already made are nonrefundable and are not prorated except where applicable law requires otherwise. Taxes may be added where required. A checkout success page does not grant Pro; access begins after a verified billing event updates the entitlement ledger.</p>
      </section>

      <section><h2>7. Support and availability</h2>
        <p>Provider will use reasonable efforts to support paid workflows but does not guarantee uninterrupted availability or a specific resolution time unless a separate order says otherwise. Diagnostics are opt-in and do not automatically contain engineering files. A suspected incorrect result must be independently reviewed and the affected workflow should not be relied upon until resolved.</p>
      </section>

      <section><h2>8. Intellectual property and feedback</h2>
        <p>Provider and its licensors retain rights in the Service, software, documentation, branding, and improvements. Customer project files and deliverables are excluded. Voluntary feedback may be used without identifying the customer or using confidential engineering data. Third-party components remain subject to their applicable notices.</p>
      </section>

      <section><h2>9. Confidentiality</h2>
        <p>Each party will protect nonpublic information received from the other using reasonable care and use it only for the Service. This does not cover information lawfully known, independently developed, lawfully received elsewhere, or public without breach. Legally required disclosure is permitted with notice where lawful.</p>
      </section>

      <section><h2>10. Warranty disclaimer</h2>
        <p><strong>TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE SERVICE, PROFILES, DOCUMENTATION, OUTPUTS, AND SUPPORT ARE PROVIDED “AS IS” AND “AS AVAILABLE.” PROVIDER DISCLAIMS IMPLIED WARRANTIES INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT, ACCURACY, ERROR-FREE OPERATION, AND FITNESS OF RESULTS FOR A PROJECT WITHOUT INDEPENDENT PROFESSIONAL VERIFICATION.</strong></p>
      </section>

      <section><h2>11. Limitation of liability</h2>
        <p><strong>TO THE MAXIMUM EXTENT PERMITTED BY LAW, NEITHER PARTY IS LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, PUNITIVE, OR CONSEQUENTIAL DAMAGES, OR LOST PROFITS, REVENUE, BUSINESS, GOODWILL, OR DATA. EACH PARTY&apos;S TOTAL AGGREGATE LIABILITY RELATED TO THE SERVICE WILL NOT EXCEED THE FEES PAID OR PAYABLE FOR THE SERVICE DURING THE 12 MONTHS BEFORE THE EVENT GIVING RISE TO LIABILITY.</strong></p>
        <p>These limitations do not apply where liability cannot legally be limited.</p>
      </section>

      <section><h2>12. Customer indemnity</h2>
        <p>The customer will defend and indemnify Provider and its personnel against third-party claims arising from unlawful use, customer-provided materials, violation of these Terms, or engineering decisions and deliverables issued without the independent professional verification required above, except to the extent caused by Provider&apos;s gross negligence or willful misconduct.</p>
      </section>

      <section><h2>13. Suspension and termination</h2>
        <p>Provider may suspend paid actions to address a security threat, unlawful use, shared credentials, or nonpayment. At termination, paid entitlements end subject to any displayed grace period. Customer local files remain under customer control and are not remotely deleted or changed.</p>
      </section>

      <section><h2>14. General terms</h2>
        <p>The governing law and legal venue are those identified by the seller at checkout or in a separately signed order. These Terms and an applicable order form are the complete agreement for the Service. An order form controls only where it expressly changes these Terms. Invalid provisions will be limited as necessary while the remainder continues. Electronic acceptance is valid.</p>
        <p>Material changes will be posted with a new effective date and additional notice when required. Legal and support contact information is provided on the customer&apos;s Stripe receipt and billing portal.</p>
      </section>
    </LegalShell>
  );
}
