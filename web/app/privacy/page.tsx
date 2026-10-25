import type { Metadata } from "next";
import LegalShell from "../LegalShell";
import { PRIVACY_EFFECTIVE_DATE } from "@/lib/billing/legal";

export const metadata: Metadata = {
  title: "Privacy Policy",
  alternates: { canonical: "https://vericivil.com/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalShell title="Privacy Policy" effectiveDate={PRIVACY_EFFECTIVE_DATE}>
      <p>This Policy explains how CW Aerial Media LLC (<strong>Provider</strong>), operating under the VeriCivil brand, handles personal information for the Superelevation Calculator Service.</p>

      <section><h2>1. Local calculations and engineering analytics</h2>
        <p><strong>Project files, project names, LandXML, engineering inputs, calculations, stationing, coordinates, project JSON, PDF reports, ORD CSV exports, and overlay DXF files are not automatically uploaded to authentication, billing, or entitlement services.</strong></p>
        <p>Calculations and exports run on your device. Separately, successful superelevation calculations send the selected DOT standard/revision, exact speed and radius, and PC/PT stationing as entered to product analytics. These statistics are not linked to accounts or browser session identifiers.</p>
        <p>LandXML retention for product improvement is enabled by default and disclosed beside the file selector. Uncheck the retention control before selecting a file to prevent transmission of its contents; local import and calculation still work. When enabled, successfully parsed files up to 1 MiB may be retained in administrator-only storage. Raw files can contain project names, author details, coordinates, and confidential project information. Only provide files you have permission to share. Original filenames are not separately collected. Embedded LandXML in saved JSON projects is not separately uploaded for retention.</p>
      </section>

      <section><h2>2. Information collected</h2>
        <p>The Free calculator does not require a Superelevation Calculator account. Hosting and security providers may process limited connection data such as IP address, browser type, device type, requested pages, timestamps, and security events.</p>
        <p>Privacy-preserving product analytics record calculator opens, calculation successes/failures, and exports using daily hashed browser session identifiers. Separate engineering statistics collect the fields listed above without account or session linkage. LandXML copies are retained only when the file retention control permits transmission. Analytics do not separately store account identifiers, IP addresses, browser details, or calculated results with engineering statistics or retained files. Raw file contents are not anonymous and may contain identifying information.</p>
        <p>Analytics requests include same-site sign-in cookies so the Service can exclude signed-in administrator activity before storage. Account identifiers are not added to analytics records.</p>
        <p>For paid accounts, Provider and WorkOS process name, email, authentication method, verification and session events, organization if supplied, internal account identifier, plan, entitlement status, named-seat information, acceptance versions, and account-security events. WorkOS provides branded identity verification and does not receive engineering files or calculations.</p>
        <p>Stripe directly processes payment-card and billing information. Provider receives transaction identifiers, plan, amount, currency, payment and renewal status, and limited billing contact information—not complete card numbers or security codes.</p>
        <p>Support information may include communications, application and engine versions, criteria metadata, operating environment, entitlement status, and redacted logs. Diagnostics do not automatically include project files or exports.</p>
      </section>

      <section><h2>3. Uses</h2>
        <p>Information is used to provide and secure the Service, authenticate users, administer plans and seats, process payments and cancellation, provide support, maintain acceptance and audit records, prevent misuse, and comply with law. Engineering statistics and retained LandXML are used to understand standards and calculation workflows, investigate import compatibility, and improve the Service.</p>
        <p>Engineering files and calculations are not sold or used for advertising.</p>
      </section>

      <section><h2>4. Disclosures</h2>
        <p>Limited personal information may be disclosed to WorkOS for authentication, Stripe for billing, and hosting, email, support, security, accounting, and professional-service providers as needed to operate the Service; to an organization administrator for its seats; when legally required or necessary to protect rights and safety; during a business transaction; or at the user&apos;s direction.</p>
        <p>Provider does not sell personal information for money or share it for cross-context behavioral advertising.</p>
      </section>

      <section><h2>5. Retention and security</h2>
        <p>Calculator-usage counters and engineering statistics expire after 90 days. Retained LandXML expires after 30 days and cannot be downloaded through the admin page after expiry. Expired engineering records and files are purged on the next engineering analytics collection or admin report request. Storage is limited to 100 retained files and 10,000 daily input combinations. Provider backups may persist according to hosting-provider retention. Account, transaction, acceptance, entitlement, support, and security records are retained only as reasonably necessary to provide the Service, meet tax and accounting duties, resolve disputes, and protect accounts.</p>
        <p>Reasonable administrative and technical safeguards are used, including limited access, secure authentication, encrypted transmission, minimal collection, redacted diagnostics, and incident handling. No system is completely secure. Users remain responsible for devices, credentials, local files, and backups.</p>
      </section>

      <section><h2>6. User choices and rights</h2>
        <p>Users may manage billing and cancellation through the account page and Stripe portal, choose whether to send diagnostics, and control local browser storage. Clearing browser storage may remove local settings or unsaved work.</p>
        <p>The LandXML retention choice is saved in this browser when storage is available. Disable it before selecting a file to prevent future retention. Disabling retention does not delete copies already received. The import status reports whether retention was confirmed; unavailable retention never prevents local calculations. Browsers signaling Do Not Track do not send engineering statistics or LandXML copies.</p>
        <p>Applicable law may provide rights to access, correct, delete, or obtain a copy of personal information, or appeal a denied request. Privacy and security contact information is provided on a paid customer&apos;s receipt and billing portal. Identity may be verified before a request is completed.</p>
      </section>

      <section><h2>7. Cookies and browser storage</h2>
        <p>The Service uses temporary browser session storage to create a random analytics identifier. The server stores only a daily one-way hash of that identifier, so activity is not linked across days. Browsers signaling Do Not Track do not send product-analytics events. The Service may also use technologies necessary for authentication, security, entitlement continuity, preferences, and operation. It does not use advertising cookies or cross-site behavioral tracking. This Policy will be updated before that practice changes.</p>
      </section>

      <section><h2>8. Children, international use, and third parties</h2>
        <p>The Service is intended for professionals and not directed to children under 13. It is operated from the United States. Third-party links and services, including Stripe and standards agencies, follow their own privacy notices.</p>
      </section>

      <section><h2>9. Changes</h2>
        <p>This Policy may change as the Service, vendors, or law changes. The revised effective date will be posted, with additional notice or consent where required.</p>
      </section>
    </LegalShell>
  );
}
