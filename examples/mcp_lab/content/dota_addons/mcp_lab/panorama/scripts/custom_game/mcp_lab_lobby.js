"use strict";

// Stage 11: own lobby. Values live in the net table "mcp_lab_flow" (key "lobby"), written only by Lua after it has
// checked the sender's host privileges; the buttons are disabled for everyone but the host.
var LIVES = [ 3, 5, 10, 0 ];
var LOOKS = [ "mage", "roshan" ];
var shown = { lives: -1, look: "" };

function IsHost()
{
	var info = Game.GetLocalPlayerInfo();
	return !!( info && info.player_has_host_privileges );
}

function HostName()
{
	var ids = Game.GetAllPlayerIDs();
	for ( var i = 0; i < ids.length; i++ )
	{
		var info = Game.GetPlayerInfo( ids[i] );
		if ( info && info.player_has_host_privileges )
			return info.player_name;
	}
	return "?";
}

function ShowSettings( data )
{
	if ( !data ) return;
	shown.lives = Number( data.lives );
	shown.look = String( data.look );
	for ( var i = 0; i < LIVES.length; i++ )
		$( "#Lives" + LIVES[i] ).SetHasClass( "Selected", LIVES[i] === shown.lives );
	for ( var j = 0; j < LOOKS.length; j++ )
		$( "#Look" + LOOKS[j] ).SetHasClass( "Selected", LOOKS[j] === shown.look );
}

// Same path for a mouse click and for the autotest: the client only asks, Lua decides
function Choose( key, value )
{
	if ( !IsHost() ) return;
	GameEvents.SendCustomGameEventToServer( "mcp_lab_lobby_set", { key: key, value: value } );
}

function OnStartPressed()
{
	if ( !IsHost() ) return;
	Game.SetAutoLaunchEnabled( false );
	Game.SetRemainingSetupTime( 1 );
}

function Update()
{
	var host = IsHost();
	$.GetContextPanel().SetHasClass( "IsHost", host );
	var buttons = $( "#LivesOptions" ).Children().concat( $( "#LookOptions" ).Children() );
	for ( var i = 0; i < buttons.length; i++ )
		buttons[i].enabled = host;
	$( "#StartButton" ).visible = host;
	$( "#HostNote" ).text = host ? $.Localize( "#mcp_lab_lobby_host_you" )
		: $.Localize( "#mcp_lab_lobby_host_other" ).replace( "%name%", HostName() );

	if ( host && Game.GetUnassignedPlayerIDs().length > 0 )
		Game.AutoAssignPlayersToTeams();

	var left = Game.GetStateTransitionTime() - Game.GetGameTime();
	$( "#Countdown" ).text = Game.GetStateTransitionTime() >= 0
		? $.Localize( "#mcp_lab_lobby_countdown" ).replace( "%s%", String( Math.max( 0, Math.ceil( left ) ) ) )
		: $.Localize( "#mcp_lab_lobby_waiting" );
	$.Schedule( 0.1, Update );
}

function OnProbe( data )
{
	var first = $( "#Lives3" );
	GameEvents.SendCustomGameEventToServer( "mcp_lab_lobby_ack", {
		ping: data.ping,
		host: IsHost() ? 1 : 0,
		buttons_enabled: first.enabled ? 1 : 0,
		lives: shown.lives,
		look: shown.look
	} );
}

( function ()
{
	LIVES.forEach( function ( n ) { $( "#Lives" + n ).SetPanelEvent( "onactivate", function () { Choose( "lives", n ); } ); } );
	LOOKS.forEach( function ( l ) { $( "#Look" + l ).SetPanelEvent( "onactivate", function () { Choose( "look", l ); } ); } );
	$( "#StartButton" ).SetPanelEvent( "onactivate", OnStartPressed );

	ShowSettings( CustomNetTables.GetTableValue( "mcp_lab_flow", "lobby" ) );
	CustomNetTables.SubscribeNetTableListener( "mcp_lab_flow", function ( table, key, data ) { if ( key === "lobby" ) ShowSettings( data ); } );
	GameEvents.Subscribe( "mcp_lab_lobby_probe", OnProbe );
	GameEvents.Subscribe( "mcp_lab_lobby_autochoose", function ( data ) { Choose( "lives", data.lives ); Choose( "look", data.look ); } );
	GameEvents.Subscribe( "mcp_lab_lobby_start", OnStartPressed );
	Update();
	$.Msg( "[MCP_LAB] lobby script loaded" );
} )();
