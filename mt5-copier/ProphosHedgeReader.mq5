//+------------------------------------------------------------------+
//| ProphosHedgeReader.mq5                                           |
//| NUR LESEN. Dieser EA laeuft im PROP-Terminal und schreibt den     |
//| kompletten Positionsstand in eine Datei im gemeinsamen Ordner.    |
//| Er enthaelt KEINE Handelsfunktion — kein OrderSend, kein Trade-   |
//| Objekt. Auf dem Prop-Konto kann er strukturell nichts veraendern. |
//|                                                                  |
//| Zusaetzliche Absicherung: "Algo Trading" im Prop-Terminal darf    |
//| AUS bleiben. EAs laufen trotzdem und duerfen Dateien schreiben,   |
//| aber das Terminal blockt jede Order — doppelt abgesichert.        |
//|                                                                  |
//| Der Executor (Python, haengt nur am LIVE-Terminal) liest diese    |
//| Datei und stellt den Hedge darauf ein.                           |
//+------------------------------------------------------------------+
#property copyright "Prophos"
#property version   "1.00"
#property strict

input string InpFileName   = "prophos_master.csv"; // Datei im gemeinsamen Ordner
input int    InpTimerMs    = 200;                  // Heartbeat-Intervall (ms)

long   g_seq = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   // Instanz-Sperre: das EA darf pro Zieldatei nur EINMAL laufen. Ohne diese
   // Pruefung schrieben zwei Charts desselben Terminals mit je eigenem g_seq
   // in dieselbe Datei — der Staleness-Detektor des Copiers wurde dadurch blind
   // (Audit 13.08.2026).
   string lockName = "PHR_" + InpFileName;
   if(GlobalVariableCheck(lockName) && (TimeCurrent() - (datetime)GlobalVariableGet(lockName)) < 30)
   {
      PrintFormat("ABBRUCH: ProphosHedgeReader laeuft bereits fuer '%s' (anderer Chart?). "
                  "Pro Datei nur EINE Instanz aufziehen.", InpFileName);
      return(INIT_FAILED);
   }
   GlobalVariableTemp(lockName);
   GlobalVariableSet(lockName, (double)TimeCurrent());

   if(!EventSetMillisecondTimer(InpTimerMs))
   {
      Print("FEHLER: Timer konnte nicht gesetzt werden");
      return(INIT_FAILED);
   }
   PrintFormat("ProphosHedgeReader gestartet — Konto %I64d @ %s · Datei %s (nur lesend)",
               AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), InpFileName);
   WriteSnapshot();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   GlobalVariableDel("PHR_" + InpFileName);
   Print("ProphosHedgeReader beendet, reason=", reason);
}

//+------------------------------------------------------------------+
//| Heartbeat: regelmaessiger Voll-Snapshot. Bewusst NICHT nur        |
//| ereignisgesteuert — laut MQL5-Doku ist die Reihenfolge der        |
//| Trade-Transaktionen nicht garantiert und die Queue (1024) kann    |
//| ueberlaufen. Der periodische Voll-Snapshot ist die Wahrheit.      |
//+------------------------------------------------------------------+
void OnTimer()
{
   WriteSnapshot();
}

//+------------------------------------------------------------------+
//| Zusaetzlich sofort bei jeder Trade-Transaktion — damit ein neuer  |
//| Trade nicht bis zum naechsten Timer-Tick wartet.                 |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   WriteSnapshot();
}

//+------------------------------------------------------------------+
//| Snapshot schreiben: erst in eine temporaere Datei, dann per       |
//| FileMove an ihren Platz — so liest der Executor nie eine halb     |
//| geschriebene Datei. Zusaetzlich Sequenznummer + Zeilenzahl +      |
//| Footer, damit eine unvollstaendige Datei erkennbar ist.           |
//+------------------------------------------------------------------+
void WriteSnapshot()
{
   g_seq++;
   // tmp-Name traegt die Kontonummer: vergisst jemand bei einem zweiten Master
   // den InpFileName zu aendern, kollidieren wenigstens die Zwischendateien
   // nicht mehr (FileOpen ist exklusiv — zwei EAs auf derselben .tmp hiessen
   // dauernd fehlgeschlagene Snapshots, genau waehrend des Trades).
   string tmp = InpFileName + "." + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".tmp";

   int h = FileOpen(tmp, FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("FEHLER: FileOpen(%s) fehlgeschlagen, error=%d", tmp, GetLastError());
      return;
   }

   int total = PositionsTotal();

   // Kopfzeile: Format-Kennung, Sequenz, Zeit, Konto, Server, Margin-Modus, Anzahl,
   // Balance, Equity, Waehrung.
   // v3 (15.08.2026, Etappe 3): Balance/Equity/Waehrung hinten ANGEHAENGT, damit
   // Prophos den Master-P&L ueber das Balance-Delta beweisen kann. Die Kennung
   // bleibt PROPHOS1 — der Copier toleriert 7, 9 und 10 Felder, alte EAs im Feld
   // duerfen nicht brechen.
   long marginMode = AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   FileWrite(h, StringFormat("PROPHOS1;%I64d;%I64d;%I64d;%s;%I64d;%d;%.2f;%.2f;%s",
                             g_seq,
                             (long)TimeCurrent(),
                             AccountInfoInteger(ACCOUNT_LOGIN),
                             AccountInfoString(ACCOUNT_SERVER),
                             marginMode,
                             total,
                             AccountInfoDouble(ACCOUNT_BALANCE),
                             AccountInfoDouble(ACCOUNT_EQUITY),
                             AccountInfoString(ACCOUNT_CURRENCY)));

   // Eine Zeile pro Position. contract_size mitschreiben, weil der Executor
   // die Kontraktgroesse des MASTER-Brokers nicht selbst abfragen kann
   // (er haengt nur am Live-Terminal, anderer Broker, andere Groessen).
   int written = 0;
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      string sym    = PositionGetString(POSITION_SYMBOL);
      long   ptype  = PositionGetInteger(POSITION_TYPE);          // 0=BUY, 1=SELL
      double vol    = PositionGetDouble(POSITION_VOLUME);
      long   ident  = PositionGetInteger(POSITION_IDENTIFIER);    // stabiler als Ticket
      double csize  = SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE);

      FileWrite(h, StringFormat("P;%I64d;%s;%I64d;%.8f;%.8f", ident, sym, ptype, vol, csize));
      written++;
   }

   FileWrite(h, StringFormat("END;%I64d;%d", g_seq, written));
   FileFlush(h);
   FileClose(h);

   // Atomar an den endgueltigen Namen schieben
   if(!FileMove(tmp, FILE_COMMON, InpFileName, FILE_COMMON|FILE_REWRITE))
      PrintFormat("FEHLER: FileMove(%s -> %s) fehlgeschlagen, error=%d", tmp, InpFileName, GetLastError());
}
//+------------------------------------------------------------------+
