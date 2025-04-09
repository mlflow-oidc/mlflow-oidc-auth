import { Component, OnInit } from "@angular/core";
import { ActivatedRoute, Router } from "@angular/router";

import { finalize } from "rxjs";
import { TableActionEnum } from "src/app/shared/components/table/table.config";
import {
  TableActionEvent,
  TableActionModel,
} from "src/app/shared/components/table/table.interface";
import { GroupDataService } from "src/app/shared/services/data/group-data.service";
import { AdminPageRoutesEnum } from "../../../config";
import { GROUP_ACTIONS, GROUP_COLUMN_CONFIG } from "./group-permissions.config";

interface GroupModel {
  group: string;
}

@Component({
  selector: "ml-group-permissions",
  templateUrl: "./group-permissions.component.html",
  styleUrls: ["./group-permissions.component.scss"],
  standalone: false,
})
export class GroupPermissionsComponent implements OnInit {
  columnConfig = GROUP_COLUMN_CONFIG;
  dataSource: GroupModel[] = [];
  actions: TableActionModel[] = GROUP_ACTIONS;

  isLoading = false;

  constructor(
    private readonly router: Router,
    private readonly route: ActivatedRoute,
    private readonly groupDataService: GroupDataService,
  ) {}

  ngOnInit(): void {
    this.isLoading = true;
    this.groupDataService
      .getAllGroups()
      .pipe(finalize(() => (this.isLoading = false)))
      .subscribe(
        ({ groups }) => (this.dataSource = groups.map((group) => ({ group }))),
      );
  }

  handleItemAction({ action, item }: TableActionEvent<GroupModel>) {
    const actionHandlers: { [key: string]: (group: GroupModel) => void } = {
      [TableActionEnum.EDIT]: this.handleUserEdit.bind(this),
    };

    const selectedAction = actionHandlers[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleUserEdit({ group }: GroupModel): void {
    this.router.navigate([`../${AdminPageRoutesEnum.GROUP}/` + group], {
      relativeTo: this.route,
    });
  }
}
