import { Component, OnInit } from "@angular/core";
import { ActivatedRoute, Router } from "@angular/router";

import { PromptsDataService } from "src/app/shared/services";
import {
  TableActionEvent,
  TableActionModel,
} from "src/app/shared/components/table/table.interface";
import {
  PROMPT_COLUMN_CONFIG,
  PROMPT_TABLE_ACTIONS,
} from "./prompt-permissions.config";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import { PromptModel } from "src/app/shared/interfaces/prompts-data.interface";
import { AdminPageRoutesEnum } from "../../../config";
import { finalize } from "rxjs";

@Component({
  selector: "ml-prompt-permissions",
  templateUrl: "./prompt-permissions.component.html",
  styleUrls: ["./prompt-permissions.component.scss"],
  standalone: false,
})
export class PromptPermissionsComponent implements OnInit {
  columnConfig = PROMPT_COLUMN_CONFIG;
  dataSource: PromptModel[] = [];
  actions: TableActionModel[] = PROMPT_TABLE_ACTIONS;

  isLoading = false;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly promptDataService: PromptsDataService,
  ) {}

  ngOnInit(): void {
    this.isLoading = true;
    this.promptDataService
      .getAllPrompts()
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe((prompts) => {
        this.dataSource = prompts;
      });
  }

  handlePromptEdit({ name }: PromptModel) {
    this.router.navigate([`../${AdminPageRoutesEnum.PROMPT}/` + name], {
      relativeTo: this.route,
    });
  }

  handleAction({ action, item }: TableActionEvent<PromptModel>) {
    const actionMapping: { [key: string]: (item: PromptModel) => void } = {
      [TableActionEnum.EDIT]: this.handlePromptEdit.bind(this),
    };

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }
}
