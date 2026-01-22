import { useMemo, useState } from "react";
import { faVial, faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { Button } from "../../shared/components/button";
import { useSearch } from "../../core/hooks/use-search";
import { useWebhooks } from "../../core/hooks/use-webhooks";
import { useToast } from "../../shared/components/toast/use-toast";
import { IconButton } from "../../shared/components/icon-button";
import { testWebhook, deleteWebhook } from "../../core/services/webhook-service";
import { CreateWebhookModal } from "./components/create-webhook-modal";
import { EditWebhookModal } from "./components/edit-webhook-modal";
import { DeleteWebhookModal } from "./components/delete-webhook-modal";
import type { ColumnConfig } from "../../shared/types/table";
import type { Webhook } from "../../shared/types/entity";
import { WebhookStatusSwitch } from "./components/webhook-status-switch";

export default function WebhooksPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { webhooks, isLoading, error, refresh, updateLocalWebhook } = useWebhooks();
  const { showToast } = useToast();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<Webhook | null>(null);
  const [deletingWebhook, setDeletingWebhook] = useState<Webhook | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const filteredWebhooks = useMemo(() => {
    return (webhooks as Webhook[]).filter((webhook: Webhook) =>
      webhook.name.toLowerCase().includes(submittedTerm.toLowerCase())
    );
  }, [webhooks, submittedTerm]);

  const handleTest = async (webhook_id: string, name: string) => {
    try {
      const response = await testWebhook(webhook_id);
      if (response.success) {
        showToast(`Test successful for ${name}`, "success");
      } else {
        showToast(`Test failed for ${name}: ${response.error_message || " Unknown error"}`, "error");
      }
    } catch (err) {
      console.error("Failed to test webhook:", err);
      showToast(`Failed to test webhook ${name}`, "error");
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingWebhook) return;

    setIsDeleting(true);
    try {
      await deleteWebhook(deletingWebhook.webhook_id);
      showToast(`Webhook "${deletingWebhook.name}" deleted successfully`, "success");
      refresh();
      setDeletingWebhook(null);
    } catch (err) {
      console.error("Failed to delete webhook:", err);
      showToast(`Failed to delete webhook "${deletingWebhook.name}"`, "error");
    } finally {
      setIsDeleting(false);
    }
  };

  const columns: ColumnConfig<Webhook>[] = useMemo(() => [
    {
      header: "Name",
      render: (webhook) => webhook.name,
    },
    {
      header: "URL",
      render: (webhook) => (
        <span className="truncate block max-w-xs" title={webhook.url}>
          {webhook.url}
        </span>
      ),
    },
    {
      header: "Actions",
      render: (webhook) => (
        <div className="flex space-x-2">
          <IconButton
            icon={faVial}
            title="Test"
            onClick={() => handleTest(webhook.webhook_id, webhook.name)}
          />
          <IconButton
            icon={faEdit}
            title="Edit"
            onClick={() => setEditingWebhook(webhook)}
          />
          <IconButton
            icon={faTrash}
            title="Delete"
            onClick={() => setDeletingWebhook(webhook)}
          />
        </div>
      ),
    },
    {
      header: "Active",
      render: (webhook) => (
        <WebhookStatusSwitch
          webhook={webhook}
          onSuccess={(newStatus) => updateLocalWebhook(webhook.webhook_id, newStatus)}
        />
      ),
    },
  ], [updateLocalWebhook]);

  return (
    <PageContainer title="Webhooks">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading webhooks..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-4 flex items-center gap-6">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search webhooks..."
            />
            <Button
              variant="secondary"
              onClick={() => setIsCreateModalOpen(true)}
              icon={faPlus}
              className="whitespace-nowrap h-8 mb-1 mt-2"
            >
              Add webhook
            </Button>
          </div>

          <EntityListTable
            mode="object"
            data={filteredWebhooks}
            columns={columns}
            searchTerm={submittedTerm}
          />

          <CreateWebhookModal
            isOpen={isCreateModalOpen}
            onClose={() => setIsCreateModalOpen(false)}
            onSuccess={refresh}
          />

          <EditWebhookModal
            isOpen={!!editingWebhook}
            onClose={() => setEditingWebhook(null)}
            onSuccess={refresh}
            webhook={editingWebhook}
          />

          <DeleteWebhookModal
            isOpen={!!deletingWebhook}
            onClose={() => setDeletingWebhook(null)}
            onConfirm={handleConfirmDelete}
            webhook={deletingWebhook}
            isProcessing={isDeleting}
          />
        </>
      )}
    </PageContainer>
  );
}
