import { Select } from "../../../shared/components/select";
import { Input } from "../../../shared/components/input";
import {
  INTERNAL_SOURCE,
  type ServiceAccountSource,
} from "../services/service-account-source-service";

interface ServiceAccountSourceFieldsProps {
  sources: ServiceAccountSource[];
  source: string;
  subject: string;
  onSourceChange: (source: string) => void;
  onSubjectChange: (subject: string) => void;
  idPrefix: string;
}

/**
 * How a service account signs in: internal (only tokens issued for it), or through one provider,
 * whose tokens alone reach it — optionally pinned to a subject now; otherwise the provider's first
 * token binds its subject.
 */
export function ServiceAccountSourceFields({
  sources,
  source,
  subject,
  onSourceChange,
  onSubjectChange,
  idPrefix,
}: ServiceAccountSourceFieldsProps) {
  const options = (
    sources.length
      ? sources
      : [
          {
            id: INTERNAL_SOURCE,
            display_name: "Internal (issued access tokens only)",
            type: "internal",
          },
        ]
  ).map((s) => ({ value: s.id, label: s.display_name }));
  const external = source !== INTERNAL_SOURCE;

  return (
    <div className="space-y-2">
      <Select
        id={`${idPrefix}-source`}
        label="Signs in with"
        options={options}
        value={source}
        onChange={(e) => onSourceChange(e.target.value)}
      />
      <p className="text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
        {external
          ? "Only this provider's tokens reach the account, and no access token can be issued for it: its lifecycle lives in the identity provider."
          : "Only access tokens issued for the account reach it; no identity provider's token does."}
      </p>
      {external && (
        <Input
          id={`${idPrefix}-subject`}
          label="Subject (optional)"
          type="text"
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
          placeholder="repo:org/app:ref:refs/heads/main"
        />
      )}
      {external && !subject && (
        <p className="text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
          Without a subject, the first token from this provider binds its own.
        </p>
      )}
    </div>
  );
}
