import {
  predictWcMatchUseCase,
  resolveSofascoreEventUseCase,
} from "@/application/container";
import type { WcPrediction } from "@/domain/entities";

export async function predictWithOptionalSofascore(params: {
  homeTeam: string;
  awayTeam: string;
  phase: string;
  useSofascore: boolean;
  manualEventId?: number;
  kickoffDate?: string | null;
}): Promise<WcPrediction> {
  let sofascoreEventId: number | undefined;

  if (params.useSofascore) {
    if (params.manualEventId != null) {
      sofascoreEventId = params.manualEventId;
    } else if (params.kickoffDate) {
      const resolved = await resolveSofascoreEventUseCase.execute({
        homeTeam: params.homeTeam,
        awayTeam: params.awayTeam,
        date: params.kickoffDate,
      });
      sofascoreEventId = resolved.eventId;
    } else {
      throw new Error(
        "Data do jogo necessária para buscar o evento no Sofascore. Escolha um jogo da tabela oficial ou informe o ID manualmente.",
      );
    }
  }

  return predictWcMatchUseCase.execute({
    homeTeam: params.homeTeam,
    awayTeam: params.awayTeam,
    phase: params.phase,
    sofascoreEventId,
  });
}
