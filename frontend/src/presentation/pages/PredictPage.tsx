import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  getWcScheduleUseCase,
  getWcTeamsUseCase,
  getWcComboTicketUseCase,
  simulateWcMatchUseCase,
} from "@/application/container";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import {
  ModelBreakdownChart,
  ProbabilityDonut,
} from "@/presentation/components/charts/ProbabilityCharts";
import { ConfidenceBadge, ConfidenceBar } from "@/presentation/components/predictions/ConfidenceBadge";
import { ComboTicketPanel } from "@/presentation/components/predictions/ComboTicketPanel";
import { InPlayPanel } from "@/presentation/components/predictions/InPlayPanel";
import { MatchContextPanel } from "@/presentation/components/predictions/MatchContextPanel";
import { PoissonFactorsPanel } from "@/presentation/components/predictions/PoissonFactorsPanel";
import { SofascoreFeptPanel } from "@/presentation/components/predictions/SofascoreFeptPanel";
import { SofascoreToggle } from "@/presentation/components/predictions/SofascoreToggle";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { SlowLoadingPanel } from "@/presentation/components/ui/SlowLoadingPanel";
import { IconSwap, IconZap } from "@/presentation/components/ui/Icons";
import { phases, outcomeColors } from "@/presentation/theme";
import {
  awayOpponentsForHome,
  formatOfficialMatchLabel,
  findOfficialMatch,
  findReverseOfficialMatch,
  homeTeamsInSchedule,
  matchesForPhase,
  phasesInSchedule,
} from "@/presentation/utils/officialSchedule";
import { kickoffDateFromIso } from "@/presentation/utils/sofascore";
import { predictWithOptionalSofascore } from "@/presentation/utils/sofascorePredict";
import { motion } from "framer-motion";
import { useToast } from "@/presentation/components/ui/toast";
import { LineupPitchView } from "@/presentation/components/squads/LineupPitchView";
import { StandaloneEvPanel } from "@/presentation/components/predictions/StandaloneEvPanel";
import { teamColor } from "@/data/teamColors";

export function PredictPage() {
  const [searchParams] = useSearchParams();
  const [homeTeam, setHomeTeam] = useState("");
  const [awayTeam, setAwayTeam] = useState("");
  const [phase, setPhase] = useState("group");
  const [useSofascore, setUseSofascore] = useState(
    () => searchParams.get("sofascore") === "1",
  );
  const [sofascoreEventIdInput, setSofascoreEventIdInput] = useState("");
  const urlParamsApplied = useRef(false);

  const homeFromUrl = searchParams.get("home");
  const awayFromUrl = searchParams.get("away");
  const dateFromUrl = searchParams.get("date");
  const eventIdFromUrl = searchParams.get("eventId");
  const fifaMatchIdFromUrl = searchParams.get("fifaMatchId");
  const friendlyMode = searchParams.get("source") === "friendly";
  const simulateMode = searchParams.get("simulate") === "1";
  const phaseFromUrl = searchParams.get("phase");

  const scheduleQuery = useQuery({
    queryKey: ["wc-schedule"],
    queryFn: () => getWcScheduleUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const teamsQuery = useQuery({
    queryKey: ["wc-teams"],
    queryFn: () => getWcTeamsUseCase.execute(),
    enabled: friendlyMode,
    staleTime: 30 * 60_000,
  });

  const availablePhases = useMemo(() => {
    if (!scheduleQuery.data) return phases.filter((p) => p.value === "group");
    const scheduled = new Set(phasesInSchedule(scheduleQuery.data));
    return phases.filter((p) => scheduled.has(p.value));
  }, [scheduleQuery.data]);

  const phaseMatches = useMemo(
    () => (scheduleQuery.data ? matchesForPhase(scheduleQuery.data, phase) : []),
    [scheduleQuery.data, phase],
  );

  const allTeams = teamsQuery.data ?? [];

  const homeOptions = useMemo(() => {
    if (friendlyMode) {
      return allTeams.length > 0 ? allTeams : homeTeam ? [homeTeam] : [];
    }
    return homeTeamsInSchedule(phaseMatches);
  }, [friendlyMode, allTeams, homeTeam, phaseMatches]);

  const awayOptions = useMemo(() => {
    if (friendlyMode) {
      const pool = allTeams.length > 0 ? allTeams : awayTeam ? [awayTeam] : [];
      return pool.filter((t) => t !== homeTeam);
    }
    return awayOpponentsForHome(homeTeam, phaseMatches);
  }, [friendlyMode, allTeams, awayTeam, homeTeam, phaseMatches]);

  const selectedMatch = useMemo(
    () => findOfficialMatch(homeTeam, awayTeam, phaseMatches),
    [homeTeam, awayTeam, phaseMatches],
  );

  const canSwap = useMemo(() => {
    if (friendlyMode) return Boolean(homeTeam && awayTeam);
    return Boolean(findReverseOfficialMatch(homeTeam, awayTeam, phaseMatches));
  }, [friendlyMode, homeTeam, awayTeam, phaseMatches]);

  useEffect(() => {
    if (friendlyMode) return;
    if (availablePhases.length === 0) return;
    if (!availablePhases.some((p) => p.value === phase)) {
      setPhase(availablePhases[0].value);
    }
  }, [availablePhases, friendlyMode, phase]);

  useEffect(() => {
    if (urlParamsApplied.current || !friendlyMode) return;
    if (homeFromUrl) setHomeTeam(homeFromUrl);
    if (awayFromUrl) setAwayTeam(awayFromUrl);
    if (eventIdFromUrl) setSofascoreEventIdInput(eventIdFromUrl);
    setPhase(phaseFromUrl && phases.some((p) => p.value === phaseFromUrl) ? phaseFromUrl : "round_16");
    setUseSofascore(true);
    urlParamsApplied.current = true;
  }, [friendlyMode, homeFromUrl, awayFromUrl, eventIdFromUrl, phaseFromUrl]);

  useEffect(() => {
    if (urlParamsApplied.current || friendlyMode || !scheduleQuery.data) return;
    if (!homeFromUrl || !awayFromUrl) return;

    const match = findOfficialMatch(homeFromUrl, awayFromUrl, phaseMatches);
    if (match) {
      setHomeTeam(homeFromUrl);
      setAwayTeam(awayFromUrl);
      if (match.phase) {
        setPhase(match.phase);
      }
      urlParamsApplied.current = true;
    }
  }, [scheduleQuery.data, friendlyMode, homeFromUrl, awayFromUrl, phaseMatches]);

  useEffect(() => {
    if (urlParamsApplied.current || friendlyMode) return;
    if (homeOptions.length === 0) return;
    if (!homeOptions.includes(homeTeam)) {
      setHomeTeam(homeOptions[0]);
    }
  }, [homeOptions, homeTeam, friendlyMode]);

  useEffect(() => {
    if (urlParamsApplied.current || friendlyMode) return;
    if (awayOptions.length === 0) return;
    if (!awayOptions.includes(awayTeam)) {
      setAwayTeam(awayOptions[0]);
    }
  }, [awayOptions, awayTeam, friendlyMode]);

  const { addToast } = useToast();

  const manualSofascoreEventId = useMemo(() => {
    const parsed = Number.parseInt(sofascoreEventIdInput, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
  }, [sofascoreEventIdInput]);

  const resolvedSofascoreEventId = useMemo(() => {
    if (manualSofascoreEventId != null) return manualSofascoreEventId;
    const fromUrl = Number.parseInt(eventIdFromUrl ?? "", 10);
    return Number.isFinite(fromUrl) && fromUrl > 0 ? fromUrl : undefined;
  }, [manualSofascoreEventId, eventIdFromUrl]);

  const resolvedMatchDate = useMemo(() => {
    if (dateFromUrl) return dateFromUrl.slice(0, 10);
    return undefined;
  }, [dateFromUrl]);

  const superbetEventIdFromUrl = useMemo(() => {
    const parsed = Number.parseInt(searchParams.get("superbetEventId") ?? "", 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
  }, [searchParams]);

  const comboTicketQuery = useQuery({
    queryKey: ["wc-combo-ticket", homeTeam, awayTeam, superbetEventIdFromUrl],
    queryFn: () =>
      getWcComboTicketUseCase.execute({
        homeTeam,
        awayTeam,
        bankroll: 1000,
        superbetEventId: superbetEventIdFromUrl,
      }),
    enabled: Boolean(homeTeam && awayTeam),
    staleTime: 5 * 60_000,
  });

  const predictMutation = useMutation({
    mutationFn: () =>
      predictWithOptionalSofascore({
        homeTeam,
        awayTeam,
        phase,
        useSofascore,
        manualEventId: manualSofascoreEventId,
        kickoffDate: friendlyMode
          ? dateFromUrl ?? kickoffDateFromIso(selectedMatch?.kickoff)
          : kickoffDateFromIso(selectedMatch?.kickoff),
      }),
    onSuccess: () => {
      addToast(
        useSofascore ? "Palpite com escalação Sofascore gerado!" : "Palpite gerado com sucesso!",
        "success",
      );
    },
    onError: (error) => {
      addToast(
        error instanceof Error ? error.message : "Falha ao gerar palpite. Tente novamente.",
        "error",
      );
    },
  });

  const simulateMutation = useMutation({
    mutationFn: () =>
      simulateWcMatchUseCase.execute({
        homeTeam,
        awayTeam,
        phase,
        matchDate: resolvedMatchDate,
        fifaMatchId: fifaMatchIdFromUrl ?? undefined,
        sofascoreEventId: resolvedSofascoreEventId,
      }),
    onSuccess: () => {
      addToast("Análise FIFA + Sofascore gerada!", "success");
    },
    onError: (error) => {
      addToast(
        error instanceof Error ? error.message : "Falha na simulação. Tente novamente.",
        "error",
      );
    },
  });

  const useSimulateFlow = friendlyMode && simulateMode;
  const isMutationPending = useSimulateFlow
    ? simulateMutation.isPending
    : predictMutation.isPending;
  const isMutationError = useSimulateFlow ? simulateMutation.isError : predictMutation.isError;
  const mutationError = useSimulateFlow ? simulateMutation.error : predictMutation.error;

  const runMutation = () => {
    if (useSimulateFlow) {
      simulateMutation.mutate();
      return;
    }
    predictMutation.mutate();
  };

  const canPredict = friendlyMode
    ? Boolean(homeTeam && awayTeam)
    : Boolean(selectedMatch);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canPredict) {
      runMutation();
    }
  };

  const handleSwap = () => {
    if (!canSwap) return;
    setHomeTeam(awayTeam);
    setAwayTeam(homeTeam);
  };

  const matchPickerValue =
    homeTeam && awayTeam ? `${homeTeam}|${awayTeam}` : "";

  const handleMatchPicker = (value: string) => {
    const [home, away] = value.split("|");
    if (home && away) {
      setHomeTeam(home);
      setAwayTeam(away);
    }
  };

  const isLoading = friendlyMode ? teamsQuery.isLoading : scheduleQuery.isLoading;
  const hasOfficialMatches = friendlyMode || phaseMatches.length > 0;
  const friendlyKickoffHint = dateFromUrl ?? kickoffDateFromIso(selectedMatch?.kickoff);

  return (
    <PageTransition>
      <HeroPageHeader
        title={
          friendlyMode
            ? simulateMode
              ? "Palpite — amistoso (FIFA + Sofascore)"
              : "Palpite — amistoso"
            : "Palpite avulso"
        }
        subtitle={
          friendlyMode
            ? simulateMode
              ? "Escalações FIFA, rankings ao vivo e enriquecimento Sofascore"
              : "Confronto preparatório · modelos WC sem tabela oficial"
            : "Escolha um jogo da tabela oficial · Ensemble Dixon-Coles + Logística + KXL"
        }
        badges={[
          {
            label: friendlyMode ? (simulateMode ? "Amistoso · simulate" : "Amistoso") : "Copa 2026",
            color: "green",
          },
        ]}
        imageSrc="/images/predict-hero.png"
        imageOpacity={0.22}
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          {scheduleQuery.isError && (
            <ErrorState
              message={
                scheduleQuery.error instanceof Error
                  ? scheduleQuery.error.message
                  : "Falha ao carregar tabela oficial"
              }
              onRetry={() => scheduleQuery.refetch()}
            />
          )}

          {!scheduleQuery.isError && (
            <form onSubmit={handleSubmit} className="glass-card space-y-4 p-5">
              <p className="section-label">Configurar confronto</p>

              {!friendlyMode && (
                <div>
                  <label htmlFor="match-picker" className="mb-1.5 block text-xs font-medium text-slate-400">
                    Jogo oficial
                  </label>
                  {isLoading ? (
                    <Skeleton className="h-10 w-full" />
                  ) : (
                    <select
                      id="match-picker"
                      value={matchPickerValue}
                      onChange={(e) => handleMatchPicker(e.target.value)}
                      disabled={!hasOfficialMatches}
                      className="select-field"
                    >
                      {phaseMatches.map((m) => (
                        <option
                          key={m.matchId}
                          value={`${m.homeTeam}|${m.awayTeam}`}
                          className="bg-surface"
                        >
                          {formatOfficialMatchLabel(m.homeTeam, m.awayTeam, m.group, m.round)}
                        </option>
                      ))}
                    </select>
                  )}
                  <p className="mt-1.5 text-[11px] text-slate-500">
                    Ou ajuste mandante e visitante abaixo
                  </p>
                </div>
              )}

              {friendlyMode && (
                <div className="rounded-xl border border-neon-blue/20 bg-neon-blue/5 px-3 py-2 text-xs text-slate-400">
                  Amistoso internacional
                  {friendlyKickoffHint && (
                    <span className="text-slate-500"> · {friendlyKickoffHint}</span>
                  )}
                  {eventIdFromUrl && (
                    <span className="text-slate-500"> · Sofascore #{eventIdFromUrl}</span>
                  )}
                </div>
              )}

              <div>
                <label htmlFor="phase" className="mb-1.5 block text-xs font-medium text-slate-400">
                  Fase
                </label>
                {isLoading ? (
                  <Skeleton className="h-10 w-full" />
                ) : (
                  <select
                    id="phase"
                    value={phase}
                    onChange={(e) => setPhase(e.target.value)}
                    className="select-field"
                  >
                    {availablePhases.map((p) => (
                      <option key={p.value} value={p.value} className="bg-surface">
                        {p.label}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label htmlFor="home" className="mb-1.5 block text-xs font-medium text-slate-400">
                  Mandante
                </label>
                {isLoading ? (
                  <Skeleton className="h-10 w-full" />
                ) : (
                  <div className="relative">
                    <select
                      id="home"
                      value={homeTeam}
                      onChange={(e) => setHomeTeam(e.target.value)}
                      disabled={!hasOfficialMatches}
                      className="select-field pr-8"
                    >
                      {homeOptions.map((t) => (
                        <option key={t} value={t} className="bg-surface">
                          {t}
                        </option>
                      ))}
                    </select>
                    <TeamColorDot color={outcomeColors["1"]} />
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-white/5" />
                <button
                  type="button"
                  onClick={handleSwap}
                  disabled={!canSwap}
                  title={
                    canSwap
                      ? "Inverter mandante e visitante"
                      : "Este confronto invertido não existe na tabela oficial"
                  }
                  className="btn-icon disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Inverter mandante e visitante"
                >
                  <IconSwap className="h-3.5 w-3.5" />
                </button>
                <div className="h-px flex-1 bg-white/5" />
              </div>

              <div>
                <label htmlFor="away" className="mb-1.5 block text-xs font-medium text-slate-400">
                  Visitante
                </label>
                {isLoading ? (
                  <Skeleton className="h-10 w-full" />
                ) : (
                  <div className="relative">
                    <select
                      id="away"
                      value={awayTeam}
                      onChange={(e) => setAwayTeam(e.target.value)}
                      disabled={!hasOfficialMatches || awayOptions.length === 0}
                      className="select-field pr-8"
                    >
                      {awayOptions.map((t) => (
                        <option key={t} value={t} className="bg-surface">
                          {t}
                        </option>
                      ))}
                    </select>
                    <TeamColorDot color={outcomeColors["2"]} />
                  </div>
                )}
              </div>

              {selectedMatch && !friendlyMode && (
                <div className="rounded-xl border border-neon-green/15 bg-neon-green/5 px-3 py-2 text-xs text-slate-400">
                  Jogo oficial · Grupo {selectedMatch.group} · Rodada {selectedMatch.round}
                  {selectedMatch.city && (
                    <span className="text-slate-500"> · {selectedMatch.city}</span>
                  )}
                </div>
              )}

              {!friendlyMode && !hasOfficialMatches && !isLoading && (
                <p className="rounded-xl border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-400">
                  Nenhum jogo oficial nesta fase.{" "}
                  <Link to="/jogos" className="underline hover:text-amber-300">
                    Ver tabela
                  </Link>
                </p>
              )}

              <SofascoreToggle
                enabled={useSofascore}
                onChange={setUseSofascore}
                eventId={sofascoreEventIdInput}
                onEventIdChange={setSofascoreEventIdInput}
                disabled={!hasOfficialMatches}
                hint={
                  friendlyKickoffHint
                    ? `Busca automática pela data ${friendlyKickoffHint}`
                    : friendlyMode
                      ? "Informe o ID do evento Sofascore ou a data do amistoso"
                      : "Selecione um jogo da tabela para resolver o evento automaticamente"
                }
              />

              <button
                type="submit"
                disabled={isMutationPending || !canPredict}
                className="btn-primary w-full"
              >
                <IconZap className="h-4 w-4" />
                {isMutationPending
                  ? "Calculando…"
                  : friendlyMode && simulateMode
                    ? "Analisar (FIFA + Sofascore)"
                    : "Gerar palpite"}
              </button>
            </form>
          )}

          {canPredict && !isMutationPending && (
            <div className="mt-3 flex items-center justify-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-sm">
              <span className="font-semibold text-white">{homeTeam}</span>
              <span className="rounded-lg bg-white/5 px-2 py-0.5 text-xs font-bold text-slate-500">VS</span>
              <span className="font-semibold text-white">{awayTeam}</span>
            </div>
          )}
        </div>

        <div className="lg:col-span-3">
          {isMutationPending && (
            <SlowLoadingPanel
              active
              title={useSimulateFlow ? "Consultando FIFA e Sofascore…" : "Calculando palpite…"}
              hint={
                useSimulateFlow
                  ? "Buscando escalações oficiais, rankings e estatísticas recentes."
                  : "O modelo analisa histórico, forma recente e índices KXL para este confronto."
              }
              steps={
                useSimulateFlow
                  ? ["Janela FIFA", "Rankings ao vivo", "Enriquecimento Sofascore"]
                  : ["Normalizando seleções", "Rodando Dixon-Coles e logística", "Combinando ensemble final"]
              }
            />
          )}

          {isMutationError && (
            <ErrorState
              message={
                mutationError instanceof Error ? mutationError.message : "Erro na previsão"
              }
              onRetry={runMutation}
            />
          )}

          {isMutationPending && (
            <div className="glass-card space-y-4 p-6">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}

          {!simulateMutation.data &&
            !predictMutation.data &&
            !isMutationPending &&
            !isMutationError && (
            <div className="glass-card flex h-full min-h-[320px] flex-col items-center justify-center gap-4 p-8 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/[0.06] bg-white/[0.03] text-2xl font-black text-slate-700">
                VS
              </div>
              <p className="max-w-xs text-sm text-slate-500">
                {friendlyMode ? (
                  <>
                    Confronto de{" "}
                    <Link to="/amistosos" className="text-neon-green hover:underline">
                      amistoso
                    </Link>
                    . Clique em <span className="text-slate-400">Gerar palpite</span>
                  </>
                ) : (
                  <>
                    Escolha um confronto da{" "}
                    <Link to="/jogos" className="text-neon-green hover:underline">
                      tabela oficial
                    </Link>{" "}
                    e clique em <span className="text-slate-400">Gerar palpite</span>
                  </>
                )}
              </p>
            </div>
          )}

          {simulateMutation.data && useSimulateFlow && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <div className="glass-card overflow-hidden">
                <div
                  className="flex flex-wrap items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-4"
                  style={{ backgroundColor: `${outcomeColors[simulateMutation.data.prediction]}06` }}
                >
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wider">Análise integrada</p>
                    <h2 className="mt-1 text-xl font-bold text-white">
                      {simulateMutation.data.homeTeam}{" "}
                      <span className="font-normal text-slate-500">x</span>{" "}
                      {simulateMutation.data.awayTeam}
                    </h2>
                    {simulateMutation.data.fifaStadium && (
                      <p className="mt-0.5 text-xs text-slate-500">{simulateMutation.data.fifaStadium}</p>
                    )}
                  </div>
                  <ConfidenceBadge
                    confidence={simulateMutation.data.confidence}
                    prediction={simulateMutation.data.prediction}
                  />
                </div>
                <div className="p-5 space-y-5">
                  <ProbabilityDonut
                    probHome={simulateMutation.data.probHome}
                    probDraw={simulateMutation.data.probDraw}
                    probAway={simulateMutation.data.probAway}
                    prediction={simulateMutation.data.prediction}
                  />
                  {(simulateMutation.data.poissonScore ||
                    simulateMutation.data.expectedGoals) && (
                    <div className="grid grid-cols-2 gap-2">
                      <StatBox
                        label="Placar previsto"
                        value={simulateMutation.data.poissonScore ?? "—"}
                        color="green"
                      />
                      <StatBox
                        label="Gols esperados"
                        value={simulateMutation.data.expectedGoals ?? "—"}
                        color="blue"
                      />
                    </div>
                  )}
                  {(simulateMutation.data.fifaHomePoints != null ||
                    simulateMutation.data.fifaAwayPoints != null) && (
                    <div className="grid grid-cols-3 gap-2">
                      <StatBox
                        label="Pts FIFA (casa)"
                        value={simulateMutation.data.fifaHomePoints?.toFixed(1) ?? "—"}
                      />
                      <StatBox
                        label="Diferença"
                        value={simulateMutation.data.fifaPointsDiff?.toFixed(1) ?? "—"}
                        color="purple"
                      />
                      <StatBox
                        label="Pts FIFA (fora)"
                        value={simulateMutation.data.fifaAwayPoints?.toFixed(1) ?? "—"}
                      />
                    </div>
                  )}
                  <ConfidenceBar confidence={simulateMutation.data.confidence} />
                </div>
              </div>

              {(simulateMutation.data.fifaHomeLineup?.length ||
                simulateMutation.data.fifaAwayLineup?.length) && (
                <div className="glass-card space-y-5 p-5">
                  <p className="section-label">
                    Escalações · {lineupSourceLabel(simulateMutation.data.lineupSource)} · passe o
                    mouse sobre o jogador
                  </p>
                  <div className="grid gap-6 lg:grid-cols-2">
                    {simulateMutation.data.fifaHomeLineup?.length ? (
                      <div className="space-y-2">
                        <p className="text-center text-sm font-semibold text-white">
                          {simulateMutation.data.homeTeam}
                          {simulateMutation.data.fifaHomeCoach || simulateMutation.data.fifaHomeTactics
                            ? ` · ${[simulateMutation.data.fifaHomeCoach, simulateMutation.data.fifaHomeTactics].filter(Boolean).join(" · ")}`
                            : ""}
                        </p>
                        <LineupPitchView
                          team={simulateMutation.data.homeTeam}
                          teamColor={teamColor(simulateMutation.data.homeTeam)}
                          formation={simulateMutation.data.fifaHomeTactics}
                          lineup={simulateMutation.data.fifaHomeLineup}
                        />
                      </div>
                    ) : null}
                    {simulateMutation.data.fifaAwayLineup?.length ? (
                      <div className="space-y-2">
                        <p className="text-center text-sm font-semibold text-white">
                          {simulateMutation.data.awayTeam}
                          {simulateMutation.data.fifaAwayCoach || simulateMutation.data.fifaAwayTactics
                            ? ` · ${[simulateMutation.data.fifaAwayCoach, simulateMutation.data.fifaAwayTactics].filter(Boolean).join(" · ")}`
                            : ""}
                        </p>
                        <LineupPitchView
                          team={simulateMutation.data.awayTeam}
                          teamColor={teamColor(simulateMutation.data.awayTeam)}
                          formation={simulateMutation.data.fifaAwayTactics}
                          lineup={simulateMutation.data.fifaAwayLineup}
                        />
                      </div>
                    ) : null}
                  </div>
                </div>
              )}

              {simulateMutation.data.warnings.length > 0 && (
                <div className="glass-card space-y-2 p-5">
                  <p className="section-label">Avisos</p>
                  <ul className="space-y-1 text-sm text-amber-200/90">
                    {simulateMutation.data.warnings.map((warning) => (
                      <li key={warning}>• {warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </motion.div>
          )}

          {predictMutation.data && !useSimulateFlow && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <div className="glass-card overflow-hidden">
                <div
                  className="flex flex-wrap items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-4"
                  style={{ backgroundColor: `${outcomeColors[predictMutation.data.prediction]}06` }}
                >
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wider">Resultado previsto</p>
                    <h2 className="mt-1 text-xl font-bold text-white">
                      {predictMutation.data.homeTeam}{" "}
                      <span className="font-normal text-slate-500">x</span>{" "}
                      {predictMutation.data.awayTeam}
                    </h2>
                    <p className="mt-0.5 text-xs text-slate-500">{predictMutation.data.h2hSummary}</p>
                  </div>
                  <ConfidenceBadge
                    confidence={predictMutation.data.confidence}
                    prediction={predictMutation.data.prediction}
                  />
                </div>

                <div className="p-5 space-y-5">
                  <div className="grid gap-5 md:grid-cols-2">
                    <ProbabilityDonut
                      probHome={predictMutation.data.probHome}
                      probDraw={predictMutation.data.probDraw}
                      probAway={predictMutation.data.probAway}
                      prediction={predictMutation.data.prediction}
                    />
                    <ModelBreakdownChart
                      dixonColes={predictMutation.data.modelBreakdown.dixonColes}
                      logistic={predictMutation.data.modelBreakdown.logistic}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <StatBox label="Placar provável" value={predictMutation.data.poissonScore} color="green" />
                    <StatBox label="Gols esperados" value={predictMutation.data.expectedGoals} color="blue" />
                    <StatBox
                      label="Holdout 2022"
                      value={
                        predictMutation.data.modelBreakdown.holdout2022Accuracy != null
                          ? `${(predictMutation.data.modelBreakdown.holdout2022Accuracy * 100).toFixed(1)}%`
                          : "N/A"
                      }
                      color="purple"
                    />
                    <StatBox
                      label="Peso DC"
                      value={`${(predictMutation.data.modelBreakdown.ensembleWeights.dixonColes * 100).toFixed(0)}%`}
                    />
                  </div>

                  <ConfidenceBar confidence={predictMutation.data.confidence} />
                </div>
              </div>

              {predictMutation.data.modelBreakdown.poissonFactors && (
                <PoissonFactorsPanel
                  factors={predictMutation.data.modelBreakdown.poissonFactors}
                  homeTeam={predictMutation.data.homeTeam}
                  awayTeam={predictMutation.data.awayTeam}
                />
              )}

              <SofascoreFeptPanel fept={predictMutation.data.modelBreakdown.kxlFept} />

              <div className="glass-card p-5">
                <p className="section-label">Contexto pré-jogo</p>
                <MatchContextPanel prediction={predictMutation.data} />
              </div>

              <StandaloneEvPanel
                homeTeam={predictMutation.data.homeTeam}
                awayTeam={predictMutation.data.awayTeam}
                probabilities={{
                  "1": predictMutation.data.probHome,
                  X: predictMutation.data.probDraw,
                  "2": predictMutation.data.probAway,
                }}
              />
            </motion.div>
          )}

          {homeTeam && awayTeam && (
            <ComboTicketPanel
              homeTeam={homeTeam}
              awayTeam={awayTeam}
              ticket={comboTicketQuery.data ?? null}
            />
          )}

          {homeTeam && awayTeam && (
            <InPlayPanel
              homeTeam={homeTeam}
              awayTeam={awayTeam}
              phase={friendlyMode ? phase : phase}
            />
          )}
        </div>
      </div>
    </PageTransition>
  );
}

function TeamColorDot({ color }: { color: string }) {
  return (
    <span
      className="pointer-events-none absolute right-3 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full"
      style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}80` }}
      aria-hidden
    />
  );
}

function lineupSourceLabel(source: string | null): string {
  if (source === "sofascore") return "Sofascore";
  if (source === "fifa") return "FIFA";
  return "Escalação";
}

function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: "green" | "blue" | "purple";
}) {
  const colorClass =
    color === "green"
      ? "text-neon-green"
      : color === "blue"
        ? "text-neon-blue"
        : color === "purple"
          ? "text-neon-purple"
          : "text-white";

  return (
    <div className="stat-pill">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-bold ${colorClass}`}>{value}</p>
    </div>
  );
}
