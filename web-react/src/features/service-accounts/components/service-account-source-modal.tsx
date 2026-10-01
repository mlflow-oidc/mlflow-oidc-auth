import { useEffect, useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { extractErrorMessage } from "../../../core/services/http";
import { ServiceAccountSourceFields } from "./service-account-source-fields";
import {
  INTERNAL_SOURCE,
  setServiceAccountSource,
  type ServiceAccountSource,
} from "../services/service-account-source-service";

interface ServiceAccountSourceModalProps {
  /** The service account to re-point; null closes the modal. */
  username: string | null;
  currentSource: string | null | undefined;
  sources: ServiceAccountSource[];
  onClose: () => void;
  onSaved: () => void;
}

/** Change how a service account signs in. Going external revokes the tokens issued for it. */
export function ServiceAccountSourceModal({
  username,
  currentSource,
  sources,
  onClose,
  onSaved,
}: ServiceAccountSourceModalProps) {
  const [source, setSource] = useState(currentSource || INTERNAL_SOURCE);
  const [subject, setSubject] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const { showToast } = useToast();

  useEffect(() => {
    setSource(currentSource || INTERNAL_SOURCE);
    setSubject("");
  }, [username, currentSource]);

  if (!username) return null;
  const goingExternal =
    source !== INTERNAL_SOURCE &&
    (currentSource || INTERNAL_SOURCE) === INTERNAL_SOURCE;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await setServiceAccountSource(
        username,
        source,
        subject.trim() || undefined,
      );
      showToast(
        `${username} now signs in ${source === INTERNAL_SOURCE ? "with issued tokens only" : `through ${source}`}`,
        "success",
      );
      onSaved();
      onClose();
    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Failed to change how the service account signs in",
        ),
        "error",
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={!!username}
      onClose={onClose}
      title={`How ${username} signs in`}
    >
      <ServiceAccountSourceFields
        sources={sources}
        source={source}
        subject={subject}
        onSourceChange={setSource}
        onSubjectChange={setSubject}
        idPrefix="sa-source"
      />
      {goingExternal && (
        <p
          role="alert"
          className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200"
        >
          The access tokens issued for this account will be revoked.
        </p>
      )}
      <div className="flex justify-end space-x-3 pt-4">
        <Button variant="ghost" onClick={onClose} disabled={isSaving}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={() => {
            void handleSave();
          }}
          disabled={isSaving}
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>
    </Modal>
  );
}
