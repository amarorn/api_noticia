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
  IconDice,
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
        description: "Palpites Brasileirão",
      },
      {
        to: "/ao-vivo",
        label: "Ao vivo",
        Icon: IconLive,
        description: "Jogos Superbet live",
      },
      {
        to: "/central",
        label: "Central de Apostas",
        Icon: IconTrophy,
        description: "Melhores bilhetes e análise do dia",
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
        description: "Confronto + EV",
      },
      {
        to: "/noticias",
        label: "Notícias",
        Icon: IconNewspaper,
        description: "Feed com sentimento",
      },
      {
        to: "/casino",
        label: "Casino",
        Icon: IconDice,
        description: "Live casino Superbet",
      },
    ],
  },
  {
    id: "copa",
    label: "Copa · arquivo",
    items: [
      {
        to: "/jogos",
        label: "Agenda WC",
        Icon: IconCalendar,
        description: "Tabela oficial Copa 2026",
      },
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
        description: "Seleções internacionais",
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
      {
        to: "/validate",
        label: "Validação WC",
        Icon: IconSearch,
        description: "Histórico de Copas",
      },
    ],
  },
];

export const allNavItems = navGroups.flatMap((g) => g.items);
