import { useMemo } from "react";
import { faVial, faEdit, faTrash } from "@fortawesome/free-solid-svg-icons";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { useWebhooks } from "../../core/hooks/use-webhooks";
import { useToast } from "../../shared/components/toast/use-toast";
import { IconButton } from "../../shared/components/icon-button";
import { testWebhook, deleteWebhook } from "../../core/services/webhook-service";
import type { ColumnConfig } from "../../shared/types/table";
import type { Webhook } from "../../shared/types/entity";

export default function WebhooksPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { webhooks, isLoading, error, refresh } = useWebhooks();
  const { showToast } = useToast();

  const filteredWebhooks = useMemo(() => {
    return (webhooks as Webhook[]).filter((webhook: Webhook) =>
      webhook.name.toLowerCase().includes(submittedTerm.toLowerCase())
    );
  }, [webhooks, submittedTerm]);

  const handleTest = async (id: string, name: string) => {
    try {
      const response = await testWebhook(id);
      showToast(`Test successful for ${name}: ${response.message}`, "success");
    } catch (err) {
      console.error("Failed to test webhook:", err);
      showToast(`Failed to test webhook ${name}`, "error");
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete webhook "${name}"?`)) {
      try {
        await deleteWebhook(id);
        showToast(`Webhook "${name}" deleted successfully`, "success");
        refresh();
      } catch (err) {
        console.error("Failed to delete webhook:", err);
        showToast(`Failed to delete webhook "${name}"`, "error");
      }
    }
  };

  const columns: ColumnConfig<Webhook>[] = [
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
            onClick={() => handleTest(webhook.id, webhook.name)}
          />
          <IconButton
            icon={faEdit}
            title="Edit"
            onClick={() => console.log("Edit webhook:", webhook.id)}
          />
          <IconButton
            icon={faTrash}
            title="Delete"
            onClick={() => handleDelete(webhook.id, webhook.name)}
          />
        </div>
      ),
      className: "w-32",
    },
  ];

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
          <div className="mb-4">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search webhooks..."
            />
          </div>

          <EntityListTable
            mode="object"
            data={filteredWebhooks}
            columns={columns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
