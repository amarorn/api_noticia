import {
  GetBrasileiraoRoundUseCase,
} from "@/application/use-cases/brasileiraoUseCases";
import { GetHealthUseCase } from "@/application/use-cases/healthUseCases";
import {
  GetNewsAllUseCase,
  GetNewsCardsUseCase,
  GetNewsFeedUseCase,
  SyncNewsSourcesUseCase,
} from "@/application/use-cases/newsUseCases";
import {
  GetWcEditionsUseCase,
  GetWcEditionMatchesUseCase,
  ValidateHistoricalMatchUseCase,
} from "@/application/use-cases/historicalValidationUseCases";
import {
  GetValueBetsUseCase,
  GetWcGroupStandingsUseCase,
  GetWcRoundUseCase,
  GetWcScheduleUseCase,
  GetWcSquadsIndexUseCase,
  GetWcSquadUseCase,
  GetWcTeamsUseCase,
  GetWcFriendliesUseCase,
  GetSuperbetLiveUseCase,
  PredictWcCornersUseCase,
  PredictWcInPlayUseCase,
  PredictWcMatchUseCase,
  ResolveSofascoreEventUseCase,
  SimulateWcMatchUseCase,
} from "@/application/use-cases/wcUseCases";
import {
  brasileiraoRepository,
  healthRepository,
  historicalValidationRepository,
  newsRepository,
  wcRepository,
} from "@/infrastructure/repositories";

export const getWcRoundUseCase = new GetWcRoundUseCase(wcRepository);
export const getWcGroupStandingsUseCase = new GetWcGroupStandingsUseCase(wcRepository);
export const getWcScheduleUseCase = new GetWcScheduleUseCase(wcRepository);
export const getWcSquadsIndexUseCase = new GetWcSquadsIndexUseCase(wcRepository);
export const getWcSquadUseCase = new GetWcSquadUseCase(wcRepository);
export const predictWcMatchUseCase = new PredictWcMatchUseCase(wcRepository);
export const predictWcCornersUseCase = new PredictWcCornersUseCase(wcRepository);
export const predictWcInPlayUseCase = new PredictWcInPlayUseCase(wcRepository);
export const resolveSofascoreEventUseCase = new ResolveSofascoreEventUseCase(wcRepository);
export const getWcTeamsUseCase = new GetWcTeamsUseCase(wcRepository);
export const getWcFriendliesUseCase = new GetWcFriendliesUseCase(wcRepository);
export const getSuperbetLiveUseCase = new GetSuperbetLiveUseCase(wcRepository);
export const simulateWcMatchUseCase = new SimulateWcMatchUseCase(wcRepository);
export const getValueBetsUseCase = new GetValueBetsUseCase(wcRepository);
export const getBrasileiraoRoundUseCase = new GetBrasileiraoRoundUseCase(
  brasileiraoRepository,
);
export const getHealthUseCase = new GetHealthUseCase(healthRepository);
export const syncNewsSourcesUseCase = new SyncNewsSourcesUseCase(newsRepository);
export const getNewsFeedUseCase = new GetNewsFeedUseCase(newsRepository);
export const getNewsCardsUseCase = new GetNewsCardsUseCase(newsRepository);
export const getNewsAllUseCase = new GetNewsAllUseCase(newsRepository);
export const getWcEditionsUseCase = new GetWcEditionsUseCase(
  historicalValidationRepository,
);
export const getWcEditionMatchesUseCase = new GetWcEditionMatchesUseCase(
  historicalValidationRepository,
);
export const validateHistoricalMatchUseCase = new ValidateHistoricalMatchUseCase(
  historicalValidationRepository,
);
