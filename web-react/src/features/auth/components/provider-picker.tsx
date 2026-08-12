import { Button } from "../../../shared/components/button";
import {
  withNextTarget,
  type IdentityProvider,
} from "../services/provider-service";

type ProviderPickerProps = {
  providers: IdentityProvider[];
  next: string | null;
};

/**
 * One button per identity provider (issue #317).
 *
 * Rendered only when there is more than one to choose between — a single provider keeps the
 * page it has always had, with no picker chrome at all.
 *
 * Nothing here knows what kind of provider it is drawing. The label comes from the server and
 * the destination is the server's own login URL, so the SAML providers in #330 appear without
 * this component changing.
 */
export const ProviderPicker = ({ providers, next }: ProviderPickerProps) => (
  <div className="w-full flex flex-col gap-3">
    <span className="text-sm text-ui-text/60 dark:text-ui-text-dark/60 text-center">
      Sign in with
    </span>
    {providers.map((provider) => (
      <a
        key={provider.id}
        href={withNextTarget(provider.login_url, next)}
        className="w-full"
        data-testid={`provider-${provider.id}`}
      >
        <Button variant="primary" className="w-full py-2 text-base">
          {provider.display_name || provider.id}
        </Button>
      </a>
    ))}
  </div>
);

export default ProviderPicker;
