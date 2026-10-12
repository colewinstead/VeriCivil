import Stripe from "stripe";
import releaseInfo from "@/app/generated/release-info.json";
import { getBillingConfig } from "./config";
import { PRO_PRICE } from "./legal";
import { matchesProPrice } from "./pro-price";

export function getStripe() {
  const config = getBillingConfig();
  return new Stripe(config.secretKey, {
    httpClient: Stripe.createFetchHttpClient(),
    maxNetworkRetries: 2,
    appInfo: {
      name: "Superelevation Calculator",
      version: releaseInfo.application_version,
      url: "https://github.com/colewinstead/VeriCivil",
    },
  });
}

export async function verifyConfiguredProPrice(stripe: Stripe, priceId: string) {
  const price = await stripe.prices.retrieve(priceId);
  const valid = matchesProPrice(price);
  if (!valid) {
    throw new Error(`The configured Stripe price must be ${PRO_PRICE.display} USD and billed monthly.`);
  }
  return price;
}

export function stripeCustomerId(value: string | Stripe.Customer | Stripe.DeletedCustomer | null) {
  if (!value) return null;
  return typeof value === "string" ? value : value.id;
}

export function stripeSubscriptionPeriodEnd(subscription: Stripe.Subscription) {
  const ends = subscription.items.data.map((item) => item.current_period_end);
  return ends.length ? Math.max(...ends) : subscription.ended_at || subscription.created;
}
