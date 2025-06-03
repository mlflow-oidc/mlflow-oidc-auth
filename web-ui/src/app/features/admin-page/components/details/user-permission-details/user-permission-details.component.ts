import { AfterViewInit, Component, OnInit, ViewChild, OnDestroy } from '@angular/core';
import { MatTabGroup } from '@angular/material/tabs';
import { ActivatedRoute, Router } from '@angular/router';
import { filter, forkJoin, map, switchMap, tap, of, Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { ExperimentForUserModel } from 'src/app/shared/interfaces/experiments-data.interface';
import { ModelPermissionModel } from 'src/app/shared/interfaces/models-data.interface';
import {
  ExperimentsDataService,
  ModelsDataService,
  PromptsDataService,
  PermissionDataService,
  SnackBarService,
  AuthService,
} from 'src/app/shared/services';
import { UserExperimentRegexDataService } from 'src/app/shared/services/data/user-experiment-regex-data.service';
import { UserModelRegexDataService } from 'src/app/shared/services/data/user-model-regex-data.service';
import { UserPromptRegexDataService } from 'src/app/shared/services/data/user-prompt-regex-data.service';
import { PermissionModalService } from 'src/app/shared/services/permission-modal.service';
import {
  EXPERIMENT_ACTIONS,
  EXPERIMENT_COLUMN_CONFIG,
  MODEL_ACTIONS,
  MODEL_COLUMN_CONFIG,
  PROMPT_COLUMN_CONFIG,
  PROMPT_ACTIONS,
  EXPERIMENT_REGEX_COLUMN_CONFIG,
  EXPERIMENT_REGEX_ACTIONS,
  MODEL_REGEX_COLUMN_CONFIG,
  MODEL_REGEX_ACTIONS,
  PROMPT_REGEX_COLUMN_CONFIG,
  PROMPT_REGEX_ACTIONS,
} from './user-permission-details.config';
import { MatDialog } from '@angular/material/dialog';
import { AdminPageRoutesEnum } from '../../../config';
import { ManageRegexModalComponent } from 'src/app/shared/components/modals/manage-regex-modal/manage-regex-modal.component';
import { ManageRegexModalData } from 'src/app/shared/components/modals/manage-regex-modal/manage-regex-modal.interface';
import {
  ExperimentRegexPermissionModel,
  ModelRegexPermissionModel,
  PromptRegexPermissionModel,
} from 'src/app/shared/interfaces/groups-data.interface';

@Component({
  selector: 'ml-user-permission-details',
  templateUrl: './user-permission-details.component.html',
  styleUrls: ['./user-permission-details.component.scss'],
  standalone: false,
})
export class UserPermissionDetailsComponent implements OnInit, AfterViewInit, OnDestroy {
  userId: string = '';
  experimentsColumnConfig = EXPERIMENT_COLUMN_CONFIG;
  modelsColumnConfig = MODEL_COLUMN_CONFIG;
  promptsColumnConfig = PROMPT_COLUMN_CONFIG;

  experimentsDataSource: ExperimentForUserModel[] = [];
  modelsDataSource: ModelPermissionModel[] = [];
  promptsDataSource: ModelPermissionModel[] = [];
  experimentsActions: TableActionModel[] = EXPERIMENT_ACTIONS;
  modelsActions: TableActionModel[] = MODEL_ACTIONS;
  promptsActions: TableActionModel[] = PROMPT_ACTIONS;

  experimentRegexColumnConfig = EXPERIMENT_REGEX_COLUMN_CONFIG;
  experimentRegexDataSource: ExperimentRegexPermissionModel[] = [];
  experimentRegexActions = EXPERIMENT_REGEX_ACTIONS;

  modelRegexColumnConfig = MODEL_REGEX_COLUMN_CONFIG;
  modelRegexDataSource: ModelRegexPermissionModel[] = [];
  modelRegexActions = MODEL_REGEX_ACTIONS;

  promptRegexColumnConfig = PROMPT_REGEX_COLUMN_CONFIG;
  promptRegexDataSource: PromptRegexPermissionModel[] = [];
  promptRegexActions = PROMPT_REGEX_ACTIONS;

  @ViewChild('userTabs') permissionsTabs!: MatTabGroup;
  selectedSubTabIndexes: number[] = [0, 0, 0];
  private navigating = false;
  private isMainTabInit = true;
  isAdmin = true;

  private readonly tabIndexMapping: string[] = ['experiments', 'models', 'prompts'];
  private destroy$ = new Subject<void>();

  constructor(
    private readonly expDataService: ExperimentsDataService,
    private readonly modelDataService: ModelsDataService,
    private readonly promptDataService: PromptsDataService,
    private readonly permissionDataService: PermissionDataService,
    private readonly experimentRegexDataService: UserExperimentRegexDataService,
    private readonly modelRegexDataService: UserModelRegexDataService,
    private readonly promptRegexDataService: UserPromptRegexDataService,
    private readonly route: ActivatedRoute,
    private readonly permissionModalService: PermissionModalService,
    private readonly snackBarService: SnackBarService,
    private readonly router: Router,
    private readonly authService: AuthService,
    private readonly dialog: MatDialog
  ) {}

  ngOnInit(): void {
    this.userId = this.route.snapshot.paramMap.get('id') ?? '';
    this.isAdmin = this.authService.getUserInfo().is_admin;

    const mainEntityPath = this.route.parent?.snapshot.url[0]?.path;
    const subRoutePath = this.route.snapshot.url[0]?.path;

    let determinedMainTabIndex = mainEntityPath ? this.tabIndexMapping.indexOf(mainEntityPath) : -1;
    if (determinedMainTabIndex === -1) {
      determinedMainTabIndex = 0; // Default to the first main tab if entity not found or invalid
    }
    if (subRoutePath) {
      this.selectedSubTabIndexes[determinedMainTabIndex] = subRoutePath === AdminPageRoutesEnum.REGEX ? 1 : 0;
    } else {
      // Default to 'permissions' sub-tab (index 0) if subRoutePath is not present
      this.selectedSubTabIndexes[determinedMainTabIndex] = 0;
    }

    const dataObservables: any[] = [
      this.expDataService.getExperimentsForUser(this.userId),
      this.modelDataService.getModelsForUser(this.userId),
      this.promptDataService.getPromptsForUser(this.userId),
    ];

    if (this.isAdmin) {
      dataObservables.push(
        this.experimentRegexDataService.getExperimentRegexPermissionsForUser(this.userId),
        this.modelRegexDataService.getModelRegexPermissionsForUser(this.userId),
        this.promptRegexDataService.getPromptRegexPermissionsForUser(this.userId)
      );
    } else {
      dataObservables.push(of([]), of([]), of([]));
    }

    forkJoin(dataObservables)
      .pipe(takeUntil(this.destroy$))
      .subscribe((results) => {
        const [experiments, models = [], prompts = [], experimentsRegex = [], modelsRegex = [], promptsRegex = []] =
          results;

        this.experimentsDataSource = experiments as ExperimentForUserModel[];
        this.modelsDataSource = (models ?? []) as ModelPermissionModel[];
        this.promptsDataSource = (prompts ?? []) as ModelPermissionModel[];
        this.experimentRegexDataSource = experimentsRegex as ExperimentRegexPermissionModel[];
        this.modelRegexDataSource = modelsRegex as ModelRegexPermissionModel[];
        this.promptRegexDataSource = promptsRegex as PromptRegexPermissionModel[];
      });
  }

  ngAfterViewInit(): void {
    const mainEntityPath = this.route.parent?.snapshot.url[0]?.path;
    let mainTabIndexToSet = mainEntityPath ? this.tabIndexMapping.indexOf(mainEntityPath) : -1;

    if (mainTabIndexToSet === -1) {
      mainTabIndexToSet = 0; // Default to the first main tab
    }

    if (this.permissionsTabs) {
      this.permissionsTabs.selectedIndex = mainTabIndexToSet;
    }
    setTimeout(() => {
      this.isMainTabInit = false;
    }, 0);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  handleExperimentActions(event: TableActionEvent<ExperimentForUserModel>) {
    const actionMapping: {
      [key: string]: (experiment: ExperimentForUserModel) => void;
    } = {
      [TableActionEnum.EDIT]: this.handleEditUserPermissionForExperiment.bind(this),
      [TableActionEnum.REVOKE]: this.revokeExperimentPermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  revokeExperimentPermissionForUser(item: { id: string; type: PermissionTypeEnum }) {
    if (item.type !== PermissionTypeEnum.USER) {
      this.snackBarService.openSnackBar('Nothing to reset');
      return;
    }

    this.permissionDataService
      .deleteExperimentPermission({
        experiment_id: item.id,
        username: this.userId,
      })
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.expDataService.getExperimentsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((experiments) => (this.experimentsDataSource = experiments));
  }

  revokeModelPermissionForUser({ name, type }: ModelPermissionModel) {
    if (type !== PermissionTypeEnum.USER) {
      this.snackBarService.openSnackBar('Nothing to reset');
      return;
    }

    this.permissionDataService
      .deleteModelPermission({ name: name, username: this.userId })
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.modelDataService.getModelsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((models) => (this.modelsDataSource = models));
  }

  handleModelActions({ action, item }: TableActionEvent<ModelPermissionModel>) {
    const actionMapping: {
      [key: string]: (model: ModelPermissionModel) => void;
    } = {
      [TableActionEnum.EDIT]: this.handleEditUserPermissionForModel.bind(this),
      [TableActionEnum.REVOKE]: this.revokeModelPermissionForUser.bind(this),
    };

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }

  handleEditUserPermissionForModel({ name, permission, type }: ModelPermissionModel) {
    this.permissionModalService
      .openEditPermissionsModal(name, this.userId, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) => {
          const permissionData = {
            name,
            permission,
            username: this.userId,
          };

          return type === PermissionTypeEnum.FALLBACK
            ? this.permissionDataService.createModelPermission(permissionData)
            : this.permissionDataService.updateModelPermission(permissionData);
        }),
        tap(() => this.snackBarService.openSnackBar('Permissions updated successfully')),
        switchMap(() => this.modelDataService.getModelsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((models) => (this.modelsDataSource = models));
  }

  handleEditUserPermissionForExperiment({ id, permission, type }: ExperimentForUserModel) {
    this.permissionModalService
      .openEditPermissionsModal(id, this.userId, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) => {
          const permissionData = {
            experiment_id: id,
            permission,
            username: this.userId,
          };
          return type === PermissionTypeEnum.FALLBACK
            ? this.permissionDataService.createExperimentPermission(permissionData)
            : this.permissionDataService.updateExperimentPermission(permissionData);
        }),
        tap(() => this.snackBarService.openSnackBar('Permissions updated successfully')),
        switchMap(() => this.expDataService.getExperimentsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((experiments) => (this.experimentsDataSource = experiments));
  }

  handlePromptActions({ action, item }: TableActionEvent<ModelPermissionModel>) {
    const actionMapping: {
      [key: string]: (model: ModelPermissionModel) => void;
    } = {
      [TableActionEnum.EDIT]: this.handleEditUserPermissionForPrompt.bind(this),
      [TableActionEnum.REVOKE]: this.revokePromptPermissionForUser.bind(this),
    };
    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }
  handleEditUserPermissionForPrompt({ name, permission, type }: ModelPermissionModel) {
    this.permissionModalService
      .openEditPermissionsModal(name, this.userId, permission)
      .pipe(
        filter(Boolean),
        switchMap((permission) => {
          const permissionData = {
            name,
            permission,
            username: this.userId,
          };
          return type === PermissionTypeEnum.FALLBACK
            ? this.permissionDataService.createPromptPermission(permissionData)
            : this.permissionDataService.updatePromptPermission(permissionData);
        }),
        tap(() => this.snackBarService.openSnackBar('Permissions updated successfully')),
        switchMap(() => this.promptDataService.getPromptsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((models) => (this.promptsDataSource = models));
  }
  revokePromptPermissionForUser({ name, type }: ModelPermissionModel) {
    if (type !== PermissionTypeEnum.USER) {
      this.snackBarService.openSnackBar('Nothing to reset');
      return;
    }
    this.permissionDataService
      .deletePromptPermission({ name: name, username: this.userId })
      .pipe(
        tap(() => this.snackBarService.openSnackBar('Permission revoked successfully')),
        switchMap(() => this.promptDataService.getPromptsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((models) => (this.promptsDataSource = models));
  }

  handleTabSelection(index: number) {
    if (this.isMainTabInit) {
      return;
    }
    const userId = this.route.snapshot.paramMap.get('id');
    this.router.navigate([`/manage/user/${userId}/${this.tabIndexMapping[index]}/${AdminPageRoutesEnum.PERMISSIONS}`]);
  }

  handleSubTabSelection(subTabIndex: number): void {
    if (this.navigating) {
      return;
    }

    this.navigating = true;
    const mainIndex = this.permissionsTabs.selectedIndex;

    if (mainIndex === null || mainIndex < 0) {
      this.navigating = false;
      return;
    }

    const entity = this.tabIndexMapping[mainIndex];
    const subRoutePath = subTabIndex === 1 ? AdminPageRoutesEnum.REGEX : AdminPageRoutesEnum.PERMISSIONS;

    this.selectedSubTabIndexes[mainIndex] = subTabIndex;

    const userId = this.route.snapshot.paramMap.get('id');
    this.router.navigate([`/manage/user/${userId}/${entity}/${subRoutePath}`]).then(() => {
      setTimeout(() => {
        this.navigating = false;
      }, 100);
    });
  }

  openModalAddExperimentRegexPermissionToUser() {
    const modalData: ManageRegexModalData = {
      regex: '',
      permission: PermissionEnum.READ,
      priority: 100,
    };

    this.dialog
      .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
        data: modalData,
        width: '500px',
      })
      .afterClosed()
      .pipe(
        filter((result): result is ManageRegexModalData => !!result),
        switchMap((result) =>
          this.experimentRegexDataService.addExperimentRegexPermissionToUser(
            this.userId,
            result.regex,
            result.permission,
            result.priority
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Experiment regex permission added successfully')),
        switchMap(() => this.experimentRegexDataService.getExperimentRegexPermissionsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((data: ExperimentRegexPermissionModel[]) => (this.experimentRegexDataSource = data));
  }

  handleExperimentRegexActions(event: TableActionEvent<ExperimentRegexPermissionModel>) {
    const item = event.item;
    if (event.action.action === TableActionEnum.EDIT) {
      const modalData: ManageRegexModalData = {
        regex: item.regex,
        permission: item.permission as PermissionEnum,
        priority: item.priority,
      };

      this.dialog
        .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
          data: modalData,
          width: '500px',
        })
        .afterClosed()
        .pipe(
          filter((result): result is ManageRegexModalData => !!result),
          switchMap((result) =>
            this.experimentRegexDataService.updateExperimentRegexPermissionForUser(
              this.userId,
              item.regex,
              result.permission,
              result.priority,
              item.id
            )
          ),
          tap(() => this.snackBarService.openSnackBar('Experiment regex permission updated successfully')),
          switchMap(() => this.experimentRegexDataService.getExperimentRegexPermissionsForUser(this.userId)),
          takeUntil(this.destroy$)
        )
        .subscribe((data: ExperimentRegexPermissionModel[]) => (this.experimentRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.experimentRegexDataService
        .removeExperimentRegexPermissionFromUser(this.userId, event.item.id)
        .pipe(
          switchMap(() => this.experimentRegexDataService.getExperimentRegexPermissionsForUser(this.userId)),
          takeUntil(this.destroy$)
        )
        .subscribe((data: ExperimentRegexPermissionModel[]) => (this.experimentRegexDataSource = data));
    }
  }

  openModalAddModelRegexPermissionToUser() {
    const modalData: ManageRegexModalData = {
      regex: '',
      permission: PermissionEnum.READ,
      priority: 100,
    };

    this.dialog
      .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
        data: modalData,
        width: '500px',
      })
      .afterClosed()
      .pipe(
        filter((result): result is ManageRegexModalData => !!result),
        switchMap((result) =>
          this.modelRegexDataService.addModelRegexPermissionToUser(
            this.userId,
            result.regex,
            result.permission,
            result.priority
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Model regex permission added successfully')),
        switchMap(() => this.modelRegexDataService.getModelRegexPermissionsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((data: ModelRegexPermissionModel[]) => (this.modelRegexDataSource = data));
  }

  handleModelRegexActions(event: TableActionEvent<ModelRegexPermissionModel>) {
    const item = event.item;
    if (event.action.action === TableActionEnum.EDIT) {
      const modalData: ManageRegexModalData = {
        regex: item.regex,
        permission: item.permission as PermissionEnum,
        priority: item.priority,
      };
      this.dialog
        .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
          data: modalData,
          width: '500px',
        })
        .afterClosed()
        .pipe(
          filter((result): result is ManageRegexModalData => !!result),
          switchMap((result) =>
            this.modelRegexDataService.updateModelRegexPermissionForUser(
              this.userId,
              item.regex,
              result.permission,
              result.priority
            )
          ),
          tap(() => this.snackBarService.openSnackBar('Model regex permission updated successfully')),
          switchMap(() => this.modelRegexDataService.getModelRegexPermissionsForUser(this.userId)),
          takeUntil(this.destroy$)
        )
        .subscribe((data: ModelRegexPermissionModel[]) => (this.modelRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.modelRegexDataService
        .removeModelRegexPermissionFromUser(this.userId, event.item.regex)
        .pipe(
          switchMap(() => this.modelRegexDataService.getModelRegexPermissionsForUser(this.userId)),
          takeUntil(this.destroy$)
        )
        .subscribe((data: ModelRegexPermissionModel[]) => (this.modelRegexDataSource = data));
    }
  }

  openModalAddPromptRegexPermissionToUser() {
    const modalData: ManageRegexModalData = {
      regex: '',
      permission: PermissionEnum.READ,
      priority: 100,
    };

    this.dialog
      .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
        data: modalData,
        width: '500px',
      })
      .afterClosed()
      .pipe(
        filter((result): result is ManageRegexModalData => !!result),
        switchMap((result) =>
          this.promptRegexDataService.addPromptRegexPermissionToUser(
            this.userId,
            result.regex,
            result.permission,
            result.priority
          )
        ),
        tap(() => this.snackBarService.openSnackBar('Prompt regex permission added successfully')),
        switchMap(() => this.promptRegexDataService.getPromptRegexPermissionsForUser(this.userId)),
        takeUntil(this.destroy$)
      )
      .subscribe((data: PromptRegexPermissionModel[]) => (this.promptRegexDataSource = data));
  }

  handlePromptRegexActions(event: TableActionEvent<PromptRegexPermissionModel>) {
    const item = event.item;
    if (event.action.action === TableActionEnum.EDIT) {
      const modalData: ManageRegexModalData = {
        regex: item.regex,
        permission: item.permission as PermissionEnum,
        priority: item.priority,
      };
      this.dialog
        .open<ManageRegexModalComponent, ManageRegexModalData>(ManageRegexModalComponent, {
          data: modalData,
          width: '500px',
        })
        .afterClosed()
        .pipe(
          filter((result): result is ManageRegexModalData => !!result),
          switchMap((result) =>
            this.promptRegexDataService.updatePromptRegexPermissionForUser(
              this.userId,
              item.regex,
              result.permission,
              result.priority
            )
          ),
          tap(() => this.snackBarService.openSnackBar('Prompt regex permission updated successfully')),
          switchMap(() => this.promptRegexDataService.getPromptRegexPermissionsForUser(this.userId)),
          takeUntil(this.destroy$)
        )
        .subscribe((data: PromptRegexPermissionModel[]) => (this.promptRegexDataSource = data));
    } else if (event.action.action === TableActionEnum.REVOKE) {
      this.promptRegexDataService
        .removePromptRegexPermissionFromUser(this.userId, event.item.regex)
        .pipe(
          switchMap(() => this.promptRegexDataService.getPromptRegexPermissionsForUser(this.userId)),
          takeUntil(this.destroy$)
        )
        .subscribe((data: PromptRegexPermissionModel[]) => (this.promptRegexDataSource = data));
    }
  }
}
