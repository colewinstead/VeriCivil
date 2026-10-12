/** Authoritative price offered to new Pro subscribers. Existing Stripe subscriptions retain their price. */
export const PRO_PRICE = {
  currency: "usd",
  unitAmount: 99,
  interval: "month",
  display: "$0.99/month",
} as const;

type ConfiguredPrice = {
  active: boolean;
  currency: string;
  unit_amount: number | null;
  type: string;
  recurring: { interval: string; interval_count: number } | null;
};

export function matchesProPrice(price: ConfiguredPrice) {
  return price.active
    && price.currency === PRO_PRICE.currency
    && price.unit_amount === PRO_PRICE.unitAmount
    && price.type === "recurring"
    && price.recurring?.interval === PRO_PRICE.interval
    && price.recurring.interval_count === 1;
}
