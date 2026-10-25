"use strict";

// Stage 11: own EndScreen. Lua writes the stats into the net table "mcp_lab_flow" (key "end") before it sets the
// winner; the screen starts when those stats exist (at load or when they arrive), so it does not matter whether
// the engine creates this layout at game start or at post-game.
var JOKE_TIME = 7;   // the fake window closes by itself after this many seconds
var phase = "none";  // none -> joke -> reveal -> stats
var stats = null;

function FormatTime( sec )
{
	sec = Math.max( 0, Math.floor( sec ) );
	var s = sec % 60;
	return Math.floor( sec / 60 ) + ":" + ( s < 10 ? "0" : "" ) + s;
}

// Server Lua no longer runs in post-game (no thinks, listeners or console commands), so in an autotest this screen
// checks itself: the phases it went through and what it shows against the stats Lua wrote, then prints the result
var seen = [];
function SelfCheck()
{
	var r = {
		order: seen.join( ">" ) === "joke>reveal>stats",
		layers: $( "#StatsLayer" ).BHasClass( "Shown" ) && !$( "#JokeLayer" ).BHasClass( "Shown" ),
		deaths: $( "#StatDeaths" ).text === String( stats.deaths ),
		lives: $( "#StatLives" ).text === String( stats.lives_start ),
		result: $( "#ResultTitle" ).text === $.Localize( Number( stats.won ) === 1 ? "#mcp_lab_end_win" : "#mcp_lab_end_lose" ),
		winner: Game.GetGameWinner() === ( Number( stats.won ) === 1 ? DOTATeam_t.DOTA_TEAM_GOODGUYS : DOTATeam_t.DOTA_TEAM_BADGUYS )
	};
	var failed = Object.keys( r ).filter( function ( k ) { return !r[k]; } );
	$.Msg( "[MCP_LAB] AUTOTEST stage11 end screen " + ( failed.length === 0 ? "PASS" : "FAIL" ) + ": checks=6 failed=[" + failed.join( "," )
		+ "] phases=" + seen.join( ">" ) + " title=" + $( "#ResultTitle" ).text + " deaths=" + $( "#StatDeaths" ).text );
}

function SetPhase( p )
{
	phase = p;
	$( "#JokeLayer" ).SetHasClass( "Shown", p === "joke" || p === "reveal" );
	$( "#JokeLayer" ).SetHasClass( "Revealed", p === "reveal" );
	$( "#StatsLayer" ).SetHasClass( "Shown", p === "stats" );
	if ( p !== "none" ) seen.push( p );
	if ( p === "stats" && stats && Number( stats.autotest ) === 1 ) SelfCheck();
}

function FillStats()
{
	var won = Number( stats.won ) === 1;
	$( "#ResultTitle" ).text = $.Localize( won ? "#mcp_lab_end_win" : "#mcp_lab_end_lose" );
	$( "#ResultSubtitle" ).text = $.Localize( won ? "#mcp_lab_end_win_sub" : "#mcp_lab_end_lose_sub" );
	$( "#JokeReveal" ).text = $.Localize( won ? "#mcp_lab_end_joke_reveal_win" : "#mcp_lab_end_joke_reveal" );
	$.GetContextPanel().SetHasClass( "Won", won );
	$( "#StatTime" ).text = FormatTime( stats.time );
	$( "#StatLives" ).text = Number( stats.lives_start ) === 0 ? "∞" : String( stats.lives_start );
	$( "#StatDeaths" ).text = String( stats.deaths );
	$( "#StatCreeps" ).text = String( stats.creeps );
	$( "#StatTrophies" ).text = String( stats.trophies );
	$( "#StatKiller" ).text = stats.killer ? $.Localize( "#" + stats.killer ) : "—";
	$( "#StatLook" ).text = $.Localize( "#mcp_lab_lobby_look_" + stats.look );
}

// Any button of the fake window (or the timeout): short "just kidding" line, then the real screen
function OnJokeButton()
{
	if ( phase !== "joke" ) return;
	SetPhase( "reveal" );
	// Autotest: no timers — Panorama barely ticks while Dota is not the foreground window
	if ( Number( stats.autotest ) === 1 )
		SetPhase( "stats" );
	else
		$.Schedule( 1.5, function () { SetPhase( "stats" ); } );
}

function Start( data )
{
	if ( !data || stats ) return;
	stats = data;
	FillStats();
	SetPhase( "joke" );
	// Autotest: press a joke button right away through the same function as a click (no timers: Panorama barely
	// ticks while Dota is not the foreground window)
	if ( Number( data.autotest ) === 1 )
		OnJokeButton();
	else
		$.Schedule( JOKE_TIME, OnJokeButton );
}

( function ()
{
	SetPhase( "none" );
	$( "#JokeClose" ).SetPanelEvent( "onactivate", OnJokeButton );
	$( "#JokeWait" ).SetPanelEvent( "onactivate", OnJokeButton );
	Start( CustomNetTables.GetTableValue( "mcp_lab_flow", "end" ) );
	CustomNetTables.SubscribeNetTableListener( "mcp_lab_flow", function ( table, key, data ) { if ( key === "end" ) Start( data ); } );
	$.Msg( "[MCP_LAB] end screen script loaded" );
} )();
