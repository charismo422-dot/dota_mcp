"use strict";

// World-space UI: everything here follows a point in the 3D world every frame.
// Game.WorldToScreenX/Y return real screen pixels, while Panorama layout uses a 1080p-high
// coordinate space, so positions are multiplied by 1080 / screen height.

var FLOAT_LIFETIME = 1.1;      // seconds a damage number lives
var FLOAT_RISE = 70;           // pixels it drifts up
var floats = [];               // { panel, ent, born, dx }
var dialog = { npc: -1, open: false, fullText: "", shown: 0 };

function UiScale()
{
	return 1080 / Game.GetScreenHeight();
}

// Screen position (layout pixels) of a point above an entity's health bar
function AnchorAbove( ent, extraZ )
{
	if ( ent < 0 || !Entities.IsValidEntity( ent ) ) return null;
	var o = Entities.GetAbsOrigin( ent );
	var z = o[2] + Entities.GetHealthBarOffset( ent ) + ( extraZ || 0 );
	var sx = Game.WorldToScreenX( o[0], o[1], z );
	var sy = Game.WorldToScreenY( o[0], o[1], z );
	if ( sx < 0 || sy < 0 ) return null;  // behind the camera / off-screen
	var s = UiScale();
	return { x: sx * s, y: sy * s };
}

function Place( panel, pos, offsetX, offsetY )
{
	panel.style.position = Math.round( pos.x + offsetX ) + "px " + Math.round( pos.y + offsetY ) + "px 0px";
}

// ---------- Floating damage numbers ----------
var DAMAGE_CLASS = { 1: "Physical", 2: "Magical", 4: "Pure" };

function OnDamage( data )
{
	var label = $.CreatePanel( "Label", $( "#FloatLayer" ), "" );
	label.AddClass( "FloatNumber" );
	label.AddClass( DAMAGE_CLASS[ data.dtype ] || "Physical" );
	if ( data.amount >= 100 ) label.AddClass( "Big" );
	label.text = String( data.amount );
	label.hittest = false;
	floats.push( { panel: label, ent: data.ent, born: Game.Time(), dx: ( Math.random() - 0.5 ) * 50 } );
}

function UpdateFloats( now )
{
	for ( var i = floats.length - 1; i >= 0; i-- )
	{
		var f = floats[i];
		var t = ( now - f.born ) / FLOAT_LIFETIME;
		var pos = AnchorAbove( f.ent, 0 );
		if ( t >= 1 || pos === null )
		{
			f.panel.DeleteAsync( 0 );
			floats.splice( i, 1 );
			continue;
		}
		// quick pop, then ease-out rise and fade
		var ease = 1 - Math.pow( 1 - t, 3 );
		var scale = t < 0.12 ? 1.35 - t * 2.9 : 1.0;
		Place( f.panel, pos, f.dx - 20, -20 - ease * FLOAT_RISE );
		f.panel.style.opacity = String( t < 0.7 ? 1 : 1 - ( t - 0.7 ) / 0.3 );
		f.panel.style.preTransformScale2d = String( scale );
	}
}

// ---------- Overhead void charges ----------
var charges = 0;

function OnHud( data )
{
	charges = Math.floor( Math.min( 100, data.energy ) / 34 );  // 0..100 energy -> 0..3 pips (34/67/100)
	for ( var i = 0; i < 3; i++ )
	{
		$( "#Pip" + i ).SetHasClass( "Filled", i < charges );
	}
}

function UpdateOverhead()
{
	var hero = Players.GetPlayerHeroEntityIndex( Players.GetLocalPlayer() );
	var pos = AnchorAbove( hero, 0 );
	var panel = $( "#Overhead" );
	panel.SetHasClass( "Visible", pos !== null );
	if ( pos !== null ) Place( panel, pos, -36, -54 );
}

// ---------- NPC dialog ----------
function OnDialog( data )
{
	var panel = $( "#Dialog" );
	if ( data.action === "open" )
	{
		dialog.npc = data.npc;
		dialog.open = true;
		$( "#DialogSpeaker" ).text = $.Localize( data.speaker );
		$( "#Option1Text" ).text = $.Localize( data.opt1 );
		$( "#Option2Text" ).text = $.Localize( data.opt2 );
		$( "#DialogOptions" ).SetHasClass( "Hidden", false );
		StartTypewriter( $.Localize( data.text ) );
		panel.SetHasClass( "Open", true );
	}
	else if ( data.action === "reply" )
	{
		$( "#DialogOptions" ).SetHasClass( "Hidden", true );
		StartTypewriter( $.Localize( data.text ) );
	}
	else if ( data.action === "close" )
	{
		dialog.open = false;
		panel.SetHasClass( "Open", false );
	}
}

function StartTypewriter( text )
{
	dialog.fullText = text;
	dialog.shown = 0;
	$( "#DialogText" ).text = "";
}

function UpdateDialog()
{
	if ( dialog.shown < dialog.fullText.length )
	{
		dialog.shown = Math.min( dialog.fullText.length, dialog.shown + 2 );  // ~2 chars per frame
		$( "#DialogText" ).text = dialog.fullText.substring( 0, dialog.shown );
	}
	var pos = AnchorAbove( dialog.npc, 30 );
	if ( pos !== null )
	{
		var panel = $( "#Dialog" );
		Place( panel, pos, -200, -( panel.actuallayoutheight * UiScale() ) - 14 );
	}
}

function Choose( option )
{
	if ( !dialog.open || $( "#DialogOptions" ).BHasClass( "Hidden" ) ) return;
	GameEvents.SendCustomGameEventToServer( "mcp_lab_dialog_choice", { option: option } );
}

// ---------- Autotest hooks ----------
function OnProbe( data )
{
	GameEvents.SendCustomGameEventToServer( "mcp_lab_world_ack", {
		ping: data.ping,
		floats: floats.length,
		overhead: $( "#Overhead" ).BHasClass( "Visible" ) ? 1 : 0,
		dialog: dialog.open && $( "#Dialog" ).BHasClass( "Open" ) ? 1 : 0,
	} );
}

function OnAutoChoose( data )
{
	Choose( data.option );  // same path as a mouse click
}

// ---------- Main loop ----------
function Tick()
{
	var now = Game.Time();
	UpdateFloats( now );
	UpdateOverhead();
	UpdateDialog();
	$.Schedule( 0, Tick );  // every frame
}

( function ()
{
	GameEvents.Subscribe( "mcp_lab_dmg", OnDamage );
	GameEvents.Subscribe( "mcp_lab_hud", OnHud );
	GameEvents.Subscribe( "mcp_lab_dialog", OnDialog );
	GameEvents.Subscribe( "mcp_lab_world_probe", OnProbe );
	GameEvents.Subscribe( "mcp_lab_dialog_autochoose", OnAutoChoose );
	$( "#Option1" ).SetPanelEvent( "onactivate", function () { Choose( 1 ); } );
	$( "#Option2" ).SetPanelEvent( "onactivate", function () { Choose( 2 ); } );
	Tick();
	$.Msg( "[MCP_LAB] world UI script loaded" );
} )();
