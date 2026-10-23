"use strict";

// Server -> client: state of the rift (energy, kills, seconds until next wave).
// Every update is acknowledged back so the Lua autotest can prove both directions work.
function OnHudUpdate( data )
{
	var energy = Math.max( 0, Math.min( 100, data.energy ) );
	$( "#EnergyFill" ).style.width = energy + "%";
	$( "#EnergyValue" ).text = Math.floor( energy ) + "%";
	$( "#KillsValue" ).text = String( data.kills );
	$( "#WaveValue" ).text = data.next_wave >= 0 ? data.next_wave + " " + $.Localize( "#mcp_lab_hud_seconds" ) : "—";
	$( "#RiftPanel" ).SetHasClass( "EnergyFull", energy >= 100 );

	if ( data.ping !== undefined )
	{
		GameEvents.SendCustomGameEventToServer( "mcp_lab_hud_ack", { ping: data.ping } );
	}
}

// Client -> server: the button summons a wave immediately
function OnSummonPressed()
{
	GameEvents.SendCustomGameEventToServer( "mcp_lab_summon_wave", {} );
}

// Client -> server: stage 7 button plays the custom rift sounds (synthesized .wav + own .vsndevts)
function OnSoundPressed()
{
	GameEvents.SendCustomGameEventToServer( "mcp_lab_play_sound", {} );
}

// Stage 8: localization probe — the server sends token names, the client reports which ones resolve
// in the current UI language and what the HUD title actually shows
function OnLocProbe( data )
{
	var unresolved = [];
	var tokens = String( data.tokens ).split( "," );
	for ( var i = 0; i < tokens.length; i++ )
	{
		if ( tokens[i] !== "" && !$.CanLocalize( "#" + tokens[i] ) )
			unresolved.push( tokens[i] );
	}
	GameEvents.SendCustomGameEventToServer( "mcp_lab_loc_ack", {
		ping: data.ping,
		language: $.Language(),
		checked: tokens.length,
		unresolved: unresolved.join( "," ),
		title: $( "#RiftTitle" ).text,
		sample: $.Localize( "#mcp_lab_loc_check" )
	} );
}

( function ()
{
	GameEvents.Subscribe( "mcp_lab_hud", OnHudUpdate );
	GameEvents.Subscribe( "mcp_lab_loc_probe", OnLocProbe );
	$( "#SummonButton" ).SetPanelEvent( "onactivate", OnSummonPressed );
	$( "#SoundButton" ).SetPanelEvent( "onactivate", OnSoundPressed );
	$.Msg( "[MCP_LAB] HUD script loaded" );
} )();
