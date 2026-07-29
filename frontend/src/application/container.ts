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
  GetUserOpenBetsUseCase,
  RefreshOpenBetsCashoutsUseCase,
  RegisterComboProposalUseCase,
  CalculateSuperMultiplaUseCase,
  GetValueBetsUseCase,
  GetWcGroupStandingsUseCase,
  GetWcRoundUseCase,
  GetWcScheduleUseCase,
  GetWcSquadsIndexUseCase,
  GetWcSquadUseCase,
  GetWcTeamsUseCase,
  GetWcFriendliesUseCase,
  GetHandicapAnalysisUseCase,
  GetSuperbetLiveUseCase,
  GetSuperbetLiveAdviceUseCase,
  GetSuperbetEventUseCase,
  GetWcComboTicketUseCase,
  PredictWcCornersUseCase,
  PredictWcInPlayUseCase,
  PredictWcMatchUseCase,
  ResolveSofascoreEventUseCase,
  SimulateWcMatchUseCase,
  GetBasketSuperbetLiveUseCase,
  GetBasketSuperbetLiveAdviceUseCase,
  BuildBasketMultiGameTicketsUseCase,
  GetBaseballSuperbetLiveUseCase,
  GetBaseballSuperbetEventUseCase,
  GetBaseballSuperbetLiveAdviceUseCase,
  GetLiveCopilotUseCase,
  PostLiveCopilotAgentUseCase,
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
export const getHandicapAnalysisUseCase = new GetHandicapAnalysisUseCase(wcRepository);
export const resolveSofascoreEventUseCase = new ResolveSofascoreEventUseCase(wcRepository);
export const getWcTeamsUseCase = new GetWcTeamsUseCase(wcRepository);
export const getWcFriendliesUseCase = new GetWcFriendliesUseCase(wcRepository);
export const getSuperbetLiveUseCase = new GetSuperbetLiveUseCase(wcRepository);
export const getSuperbetLiveAdviceUseCase = new GetSuperbetLiveAdviceUseCase(wcRepository);
export const getSuperbetEventUseCase = new GetSuperbetEventUseCase(wcRepository);
export const getWcComboTicketUseCase = new GetWcComboTicketUseCase(wcRepository);
export const simulateWcMatchUseCase = new SimulateWcMatchUseCase(wcRepository);
export const getValueBetsUseCase = new GetValueBetsUseCase(wcRepository);
export const getUserOpenBetsUseCase = new GetUserOpenBetsUseCase(wcRepository);
export const refreshOpenBetsCashoutsUseCase = new RefreshOpenBetsCashoutsUseCase(wcRepository);
export const registerComboProposalUseCase = new RegisterComboProposalUseCase(wcRepository);
export const calculateSuperMultiplaUseCase = new CalculateSuperMultiplaUseCase(wcRepository);
export const getBasketSuperbetLiveUseCase = new GetBasketSuperbetLiveUseCase(wcRepository);
export const getBasketSuperbetLiveAdviceUseCase = new GetBasketSuperbetLiveAdviceUseCase(
  wcRepository,
);
export const buildBasketMultiGameTicketsUseCase = new BuildBasketMultiGameTicketsUseCase(
  wcRepository,
);
export const getBaseballSuperbetLiveUseCase = new GetBaseballSuperbetLiveUseCase(wcRepository);
export const getBaseballSuperbetEventUseCase = new GetBaseballSuperbetEventUseCase(wcRepository);
export const getBaseballSuperbetLiveAdviceUseCase = new GetBaseballSuperbetLiveAdviceUseCase(
  wcRepository,
);
export const getLiveCopilotUseCase = new GetLiveCopilotUseCase(wcRepository);
export const postLiveCopilotAgentUseCase = new PostLiveCopilotAgentUseCase(wcRepository);
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
