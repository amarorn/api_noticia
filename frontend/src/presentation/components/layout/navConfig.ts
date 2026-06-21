import type { ComponentType } from "react";
import {
  IconAlbum,
  IconCalendar,
  IconDashboard,
  IconHistory,
  IconLive,
  IconNewspaper,
  IconSearch,
  IconTrendingUp,
  IconTrophy,
  IconUsers,
  IconWallet,
  IconZap,
  IconTarget,
  IconFlask,
} from "@/presentation/components/ui/Icons";

export interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  Icon: ComponentType<{ className?: string }>;
  description?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    id: "principal",
    label: "Principal",
    items: [
      {
        to: "/",
        label: "Dashboard",
        end: true,
        Icon: IconDashboard,
        description: "Palpites da rodada",
      },
      {
        to: "/central",
        label: "Central de Apostas",
        Icon: IconTrophy,
        description: "Melhores bilhetes e análise do dia",
      },
      {
        to: "/ao-vivo",
        label: "Ao vivo",
        Icon: IconLive,
        description: "Jogos Superbet live",
      },
      {
        to: "/pre-jogo",
        label: "Análise Pré-Jogo",
        Icon: IconTarget,
        description: "Análise detalhada por jogo",
      },
      {
        to: "/palpite-avulso",
        label: "Palpite avulso",
        Icon: IconZap,
        description: "Confronto oficial + EV",
      },
      {
        to: "/jogos",
        label: "Agenda",
        Icon: IconCalendar,
        description: "Tabela oficial",
      },
      {
        to: "/brasileirao",
        label: "Brasileirão",
        Icon: IconTrendingUp,
        description: "Rodada nacional",
      },
    ],
  },
  {
    id: "copa",
    label: "Copa 2026",
    items: [
      {
        to: "/grupos",
        label: "Grupos",
        Icon: IconTrophy,
        description: "Classificação simulada",
      },
      {
        to: "/convocacoes",
        label: "Convocações",
        Icon: IconUsers,
        description: "Elencos oficiais",
      },
      {
        to: "/amistosos",
        label: "Amistosos",
        Icon: IconCalendar,
        description: "Datas preparatórias",
      },
      {
        to: "/album",
        label: "Álbum",
        Icon: IconAlbum,
        description: "Figurinhas KXL",
      },
    ],
  },
  {
    id: "analise",
    label: "Análise",
    items: [
      {
        to: "/historico",
        label: "Histórico",
        Icon: IconHistory,
        description: "Palpites e resultados",
      },
      {
        to: "/noticias",
        label: "Notícias",
        Icon: IconNewspaper,
        description: "Feed com sentimento",
      },
      {
        to: "/performance",
        label: "Performance",
        Icon: IconTrendingUp,
        description: "ROI e análise de apostas",
      },
      {
        to: "/query",
        label: "Query Bilhetes",
        Icon: IconTarget,
        description: "Análise inteligente de potencial",
      },
      {
        to: "/simular",
        label: "Simular Aposta",
        Icon: IconFlask,
        description: "Teste antes de apostar na Superbet",
      },
      {
        to: "/carteira",
        label: "Carteira",
        Icon: IconWallet,
        description: "CSV Superbet e reconciliação",
      },
      {
        to: "/modelos",
        label: "Modelos",
        Icon: IconSearch,
        description: "Benchmark e evolução",
      },
    ],
  },
];

export const allNavItems = navGroups.flatMap((g) => g.items);
