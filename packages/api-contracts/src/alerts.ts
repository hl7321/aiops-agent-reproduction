import type { JsonValue } from "./http";

export type AlertSourceType = "prometheus-v1" | "alertmanager-v2";
export type ActiveAlertStatus = "pending" | "firing" | "suppressed" | "unprocessed";

export interface AlertSource {
  readonly name: string;
  readonly type: AlertSourceType;
}

export interface ActiveAlert {
  readonly alertName: string;
  readonly service: string | null;
  readonly severity: string | null;
  readonly status: ActiveAlertStatus;
  readonly startsAt: string;
  readonly labels: Readonly<Record<string, string>>;
  readonly annotations: Readonly<Record<string, string>>;
  readonly source: AlertSource;
  readonly rawContext: Readonly<Record<string, JsonValue>>;
}

export interface ActiveAlertsData {
  readonly items: readonly ActiveAlert[];
}
