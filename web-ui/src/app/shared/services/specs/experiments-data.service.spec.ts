import { TestBed } from "@angular/core/testing";
import {
  HttpClientTestingModule,
  HttpTestingController,
} from "@angular/common/http/testing";
import { ExperimentsDataService } from "../data/experiments-data.service";
import { API_URL } from "src/app/core/configs/api-urls";
import {
  ExperimentsForUserModel,
  UserPermissionModel,
} from "src/app/shared/interfaces/experiments-data.interface";
import {
  PermissionEnum,
  PermissionTypeEnum,
} from "src/app/core/configs/permissions";

describe("ExperimentsDataService", () => {
  let service: ExperimentsDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [ExperimentsDataService],
    });
    service = TestBed.inject(ExperimentsDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  it("should fetch all experiments", () => {
    const mockExperiments = [
      {
        id: "1",
        name: "Experiment 1",
        tags: {},
        permission: "READ",
        type: "TYPE_A",
      },
    ];
    service.getAllExperiments().subscribe((experiments) => {
      expect(experiments).toEqual(mockExperiments);
    });

    const req = httpMock.expectOne(API_URL.ALL_EXPERIMENTS);
    expect(req.request.method).toBe("GET");
    req.flush(mockExperiments);
  });

  it("should fetch experiments for a user", () => {
    const userName = "testUser";

    const mockExperiments: ExperimentsForUserModel = {
      experiments: [
        {
          id: "854967757244196526",
          name: "experiment-manage-fallback",
          permission: PermissionEnum.MANAGE,
          type: PermissionTypeEnum.FALLBACK,
        },
        {
          id: "837485082057419745",
          name: "experiment-manage-group",
          permission: PermissionEnum.MANAGE,
          type: PermissionTypeEnum.GROUP,
        },
        {
          id: "833806752529152598",
          name: "experiment-manage-user",
          permission: PermissionEnum.MANAGE,
          type: PermissionTypeEnum.USER,
        },
      ],
    };
    const url = API_URL.EXPERIMENTS_FOR_USER.replace("${userName}", userName);

    service.getExperimentsForUser(userName).subscribe((experiments) => {
      expect(experiments).toEqual(mockExperiments.experiments);
    });

    const req = httpMock.expectOne(url);
    expect(req.request.method).toBe("GET");
    req.flush(mockExperiments);
  });

  it("should fetch users for an experiment", () => {
    const experimentName = "testExperiment";
    const mockUsers: UserPermissionModel[] = [
      {
        permission: PermissionEnum.READ,
        username: "bob@example.com",
      },
      {
        permission: PermissionEnum.MANAGE,
        username: "alice@example.com",
      },
    ];
    const url = API_URL.USERS_FOR_EXPERIMENT.replace(
      "${experimentName}",
      experimentName,
    );

    service.getUsersForExperiment(experimentName).subscribe((users) => {
      expect(users).toEqual(mockUsers);
    });

    const req = httpMock.expectOne(url);
    expect(req.request.method).toBe("GET");
    req.flush(mockUsers);
  });
});
