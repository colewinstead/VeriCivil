import { sql } from "drizzle-orm";
import { index, integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const billingUsers = sqliteTable("billing_users", {
  id: text("id").primaryKey(),
  email: text("email").notNull(),
  displayName: text("display_name"),
  identityProvider: text("identity_provider").notNull().default("workos"),
  identitySubject: text("identity_subject").notNull().default(""),
  stripeCustomerId: text("stripe_customer_id"),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [
  uniqueIndex("billing_users_email_idx").on(table.email),
  uniqueIndex("billing_users_identity_idx").on(table.identityProvider, table.identitySubject),
  uniqueIndex("billing_users_stripe_customer_idx").on(table.stripeCustomerId),
]);

export const subscriptions = sqliteTable("subscriptions", {
  stripeSubscriptionId: text("stripe_subscription_id").primaryKey(),
  userId: text("user_id").notNull(),
  stripeCustomerId: text("stripe_customer_id").notNull(),
  priceId: text("price_id").notNull(),
  plan: text("plan").notNull().default("pro"),
  status: text("status").notNull(),
  currentPeriodEnd: integer("current_period_end").notNull(),
  graceUntil: integer("grace_until").notNull(),
  cancelAtPeriodEnd: integer("cancel_at_period_end", { mode: "boolean" }).notNull().default(false),
  eventCreated: integer("event_created").notNull(),
  updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [
  index("subscriptions_user_idx").on(table.userId),
  index("subscriptions_customer_idx").on(table.stripeCustomerId),
]);

export const legalAcceptances = sqliteTable("legal_acceptances", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  termsVersion: text("terms_version").notNull(),
  privacyVersion: text("privacy_version").notNull(),
  acceptedAt: text("accepted_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const stripeEvents = sqliteTable("stripe_events", {
  eventId: text("event_id").primaryKey(),
  eventType: text("event_type").notNull(),
  eventCreated: integer("event_created").notNull(),
  processedAt: text("processed_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const manualEntitlements = sqliteTable("manual_entitlements", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  plan: text("plan").notNull().default("pro"),
  reason: text("reason").notNull(),
  expiresAt: integer("expires_at"),
  grantedBy: text("granted_by").notNull(),
  grantedAt: text("granted_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  revokedAt: text("revoked_at"),
  revokedBy: text("revoked_by"),
  termsVersion: text("terms_version").notNull(),
  privacyVersion: text("privacy_version").notNull(),
}, (table) => [
  index("manual_entitlements_user_idx").on(table.userId),
  index("manual_entitlements_granted_at_idx").on(table.grantedAt),
]);

export const preauthorizedEntitlements = sqliteTable("preauthorized_entitlements", {
  id: text("id").primaryKey(),
  email: text("email").notNull(),
  plan: text("plan").notNull().default("pro"),
  reason: text("reason").notNull(),
  expiresAt: integer("expires_at"),
  grantedBy: text("granted_by").notNull(),
  grantedAt: text("granted_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  claimedAt: text("claimed_at"),
  claimedByUserId: text("claimed_by_user_id"),
  revokedAt: text("revoked_at"),
  revokedBy: text("revoked_by"),
  termsVersion: text("terms_version").notNull(),
  privacyVersion: text("privacy_version").notNull(),
}, (table) => [
  index("preauthorized_entitlements_email_idx").on(table.email),
  index("preauthorized_entitlements_claimed_user_idx").on(table.claimedByUserId),
  index("preauthorized_entitlements_granted_at_idx").on(table.grantedAt),
]);

export const analyticsEvents = sqliteTable("analytics_events", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  eventDay: text("event_day").notNull(),
  sessionHash: text("session_hash").notNull(),
  calculatorId: text("calculator_id").notNull(),
  eventName: text("event_name").notNull(),
  eventDetail: text("event_detail").notNull().default(""),
  eventCount: integer("event_count").notNull().default(1),
  firstSeenAt: text("first_seen_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  lastSeenAt: text("last_seen_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [
  uniqueIndex("analytics_events_session_event_idx").on(table.eventDay, table.sessionHash, table.calculatorId, table.eventName, table.eventDetail),
  index("analytics_events_day_calculator_idx").on(table.eventDay, table.calculatorId),
]);

export const engineeringSamples = sqliteTable("engineering_samples", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  eventDay: text("event_day").notNull(),
  standard: text("standard").notNull(),
  speed: real("speed").notNull(),
  radius: real("radius").notNull(),
  pc: text("pc").notNull(),
  pt: text("pt").notNull(),
  sampleCount: integer("sample_count").notNull().default(1),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [uniqueIndex("engineering_samples_daily_idx").on(table.eventDay, table.standard, table.speed, table.radius, table.pc, table.pt)]);

export const retainedLandxmlFiles = sqliteTable("retained_landxml", {
  id: text("id").primaryKey(),
  content: text("content").notNull(),
  bytes: integer("bytes").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});
