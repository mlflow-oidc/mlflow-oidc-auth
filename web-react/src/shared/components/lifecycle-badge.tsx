import { describeManagedBy } from "../utils/managed-by";

const BADGE_BASE_CLASSES =
  "inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap";

const STATE_CLASSES = {
  active:
    "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800",
  inactive:
    "bg-gray-100 text-gray-600 border-gray-300 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600",
} as const;

const MANAGED_BY_CLASSES = {
  manual:
    "bg-gray-100 text-gray-600 border-gray-300 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600",
  scim:
    "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800",
  oidc:
    "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
  saml:
    "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-800",
} as const;

type StateBadgeProps = {
  variant: "state";
  active: boolean;
};

type ManagedByBadgeProps = {
  variant: "managed_by";
  managedBy: string;
};

export type LifecycleBadgeProps = StateBadgeProps | ManagedByBadgeProps;

export function LifecycleBadge(props: LifecycleBadgeProps) {
  if (props.variant === "state") {
    const bucket = props.active ? "active" : "inactive";
    return (
      <span className={`${BADGE_BASE_CLASSES} ${STATE_CLASSES[bucket]}`}>
        {props.active ? "Active" : "Inactive"}
      </span>
    );
  }

  const { label, bucket } = describeManagedBy(props.managedBy);
  return (
    <span className={`${BADGE_BASE_CLASSES} ${MANAGED_BY_CLASSES[bucket]}`}>
      {label}
    </span>
  );
}
