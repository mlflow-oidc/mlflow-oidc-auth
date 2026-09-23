import { Button } from "../../../shared/components/button";
import {
  withNextTarget,
  resolveLoginUrl,
  type IdentityProvider,
} from "../services/provider-service";

type ProviderPickerProps = {
  providers: IdentityProvider[];
  next: string | null;
  basePath: string;
};

/**
 * One button per identity provider (issue #317).
 *
 * Rendered only when there is more than one to choose between — a single provider keeps the
 * page it has always had, with no picker chrome at all.
 *
 * The destination is always the server's own login URL, whatever kind of provider it is — this
 * component never builds one. The only thing it draws differently by kind is a small muted
 * "SAML" hint (#330), because a SAML login is a form redirect through an IdP rather than the
 * OIDC flow this button always meant, and that is worth signalling before the click. An OIDC
 * button, or one of a type this picker has never heard of, renders exactly as it did before #330
 * — no label, pixel-identical.
 */
export const ProviderPicker = ({
  providers,
  next,
  basePath,
}: ProviderPickerProps) => (
  <div className="w-full flex flex-col gap-3">
    <span className="text-sm text-ui-text/60 dark:text-ui-text-dark/60 text-center">
      Sign in with
    </span>
    {providers.map((provider) => (
      // The SAML hint is a sibling of the link, not a child of it — inside the <a> it would
      // become part of the link's accessible name ("Corporate SSO SAML"), which is not the
      // label and would break name-based lookups for the button text alone.
      <div key={provider.id} className="w-full">
        <a
          href={withNextTarget(
            resolveLoginUrl(provider.login_url, basePath),
            next,
          )}
          className="w-full block"
          data-testid={`provider-${provider.id}`}
        >
          <Button variant="primary" className="w-full py-2 text-base">
            {provider.display_name || provider.id}
          </Button>
        </a>
        {provider.type === "saml" && (
          <span
            data-testid={`provider-kind-${provider.id}`}
            className="block text-center text-xs text-ui-text/50 dark:text-ui-text-dark/50 mt-1"
          >
            SAML
          </span>
        )}
      </div>
    ))}
  </div>
);

export default ProviderPicker;
