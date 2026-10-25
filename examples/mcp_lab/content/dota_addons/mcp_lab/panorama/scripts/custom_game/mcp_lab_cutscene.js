"use strict";

// Stage 10 cutscene overlay. Lua drives the timeline and the camera position; this script hides the stock HUD
// (and the other custom layouts), draws letterbox bars, slides with zoom-in and shake, typewriter subtitles,
// zooms the camera on request and reports a 1 s hold of SPACE as a skip.

var HOLD_TO_SKIP = 1.0;     // seconds
var ZOOM_PER_SECOND = 0.012; // slow "Ken Burns" zoom-in of the shown slide
var SHAKE_TIME = 0.9;       // seconds a shake takes to calm down
var TYPE_SPEED = 40;        // subtitle characters per second
var DEFAULT_DISTANCE = 1134;

var root = $.GetContextPanel();
var state = {
	active: false, slide: "", slideShownAt: 0, sub: "", subText: "", subStart: 0,
	shakePower: 0, shakeAt: 0, shakeOffset: 0, zoom: 1,
	camFrom: DEFAULT_DISTANCE, camTo: DEFAULT_DISTANCE, camStart: 0, camTime: 0, distance: DEFAULT_DISTANCE,
	holdStart: -1, skipSent: false, hidden: []
};

function Now() { return Game.Time(); }

// ---------- stock HUD and the other custom layouts ----------
function HudRoot()
{
	var p = root;
	while ( p.GetParent() ) p = p.GetParent();
	return p;
}

function StockHud() { return HudRoot().FindChildTraverse( "HUDElements" ); }

function SetHudVisible( visible )
{
	if ( !visible )
	{
		state.hidden = [];
		var hud = StockHud();
		if ( hud && hud.visible ) state.hidden.push( hud );
		// $.GetContextPanel() is this layout's CustomUIElement; its siblings in CustomUIContainer_Hud
		// are the other custom layouts (rift HUD, world-space UI)
		var mine = root;
		var holder = root.GetParent();
		if ( holder )
		{
			for ( var i = 0; i < holder.GetChildCount(); i++ )
			{
				var c = holder.GetChild( i );
				if ( c !== mine && c.visible ) state.hidden.push( c );
			}
		}
		for ( var j = 0; j < state.hidden.length; j++ ) state.hidden[j].visible = false;
	}
	else
	{
		for ( var k = 0; k < state.hidden.length; k++ ) if ( state.hidden[k].IsValid() ) state.hidden[k].visible = true;
		state.hidden = [];
	}
}

// ---------- timeline events from Lua ----------
function OnStart( data )
{
	state.active = true;
	state.skipSent = false;
	state.holdStart = -1;
	SetHudVisible( false );
	root.AddClass( "Active" );
	ShowSlide( "" );
	SetCamera( 900, 900, 0 );
}

function OnShot( data )
{
	ShowSlide( data.slide || "" );
	state.sub = data.sub;
	state.subText = $.Localize( data.sub );
	state.subStart = Now();
	$( "#Subtitle" ).text = "";
}

function OnShake( data )
{
	state.shakePower = data.power;
	state.shakeAt = Now();
}

function OnCamera( data ) { SetCamera( data.from, data.to, data.time ); }

function OnEnd( data )
{
	state.active = false;
	state.holdStart = -1;
	root.RemoveClass( "Active" );
	ShowSlide( "" );
	$( "#Subtitle" ).text = "";
	SetCamera( DEFAULT_DISTANCE, DEFAULT_DISTANCE, 0 );
	SetHudVisible( true );
}

function ShowSlide( name )
{
	var names = [ "rift", "mage", "hunters" ];
	for ( var i = 0; i < names.length; i++ ) $( "#Slide_" + names[i] ).SetHasClass( "Shown", names[i] === name );
	state.slide = name;
	state.slideShownAt = Now();
}

function SetCamera( from, to, time )
{
	state.camFrom = from;
	state.camTo = to;
	state.camStart = Now();
	state.camTime = time;
	if ( time <= 0 ) { state.distance = to; GameUI.SetCameraDistance( to ); }
}

// ---------- hold to skip ----------
function HoldStart() { if ( state.active && state.holdStart < 0 ) state.holdStart = Now(); }
function HoldEnd() { state.holdStart = -1; }

function HoldProgress() { return state.holdStart < 0 ? 0 : Math.min( 1, ( Now() - state.holdStart ) / HOLD_TO_SKIP ); }

// ---------- per-frame animation ----------
function Tick()
{
	if ( state.active )
	{
		var t = Now();
		// camera distance lerp
		if ( state.camTime > 0 )
		{
			var k = Math.min( 1, ( t - state.camStart ) / state.camTime );
			k = k * k * ( 3 - 2 * k );
			state.distance = Math.round( state.camFrom + ( state.camTo - state.camFrom ) * k );
			GameUI.SetCameraDistance( state.distance );
			if ( k >= 1 ) state.camTime = 0;
		}
		// slide zoom-in and shake (on the frame, so the next slide starts steady)
		state.zoom = state.slide !== "" ? 1 + ZOOM_PER_SECOND * ( t - state.slideShownAt ) : 1;
		if ( state.slide !== "" ) $( "#Slide_" + state.slide ).style.preTransformScale2d = state.zoom.toFixed( 4 );
		var s = Math.max( 0, 1 - ( t - state.shakeAt ) / SHAKE_TIME );
		var power = state.shakePower * s * s;
		var dx = ( Math.random() * 2 - 1 ) * power, dy = ( Math.random() * 2 - 1 ) * power;
		state.shakeOffset = Math.abs( dx ) + Math.abs( dy );
		$( "#SlideFrame" ).style.position = dx.toFixed( 1 ) + "px " + dy.toFixed( 1 ) + "px 0px";
		// typewriter subtitle
		var shown = Math.min( state.subText.length, Math.floor( ( t - state.subStart ) * TYPE_SPEED ) );
		$( "#Subtitle" ).text = state.subText.substring( 0, shown );
		// skip ring
		var hold = HoldProgress();
		$( "#SkipFill" ).style.width = ( hold * 100 ).toFixed( 1 ) + "%";
		if ( hold >= 1 && !state.skipSent )
		{
			state.skipSent = true;
			GameEvents.SendCustomGameEventToServer( "mcp_lab_cut_skip", { held: Now() - state.holdStart } );
		}
	}
	$.Schedule( 0, Tick );
}

// ---------- autotest hooks ----------
function OnProbe( data )
{
	var hud = StockHud();
	var cam = GameUI.GetCameraLookAtPosition();
	var shownSlide = state.slide !== "" ? $( "#Slide_" + state.slide ) : null;
	GameEvents.SendCustomGameEventToServer( "mcp_lab_cut_ack", {
		ping: data.ping,
		hud_found: hud ? 1 : 0,
		hud_visible: hud && hud.visible ? 1 : 0,
		overlay: root.BHasClass( "Active" ) ? 1 : 0,
		bars: root.BHasClass( "Active" ) ? 1 : 0,
		hidden: state.hidden.length,
		slide: state.slide,
		slide_opacity: shownSlide && shownSlide.BHasClass( "Shown" ) ? 1 : 0,
		zoom: state.zoom,
		shake: state.shakeOffset,
		sub: state.sub,
		sub_len: $( "#Subtitle" ).text.length,
		distance: state.distance,
		cam_x: cam ? cam[0] : 0,
		cam_y: cam ? cam[1] : 0
	} );
}

// Same code path as pressing and releasing SPACE
function OnAutoHold( data )
{
	HoldStart();
	$.Schedule( data.seconds, HoldEnd );
}

( function()
{
	// Console commands outlive this script (layout reload, map relaunch) and cannot be re-created, so an old name
	// would keep calling a dead script: every load registers a fresh name and binds SPACE to it
	var cmd = "mcp_lab_cut_skip_" + Math.floor( Math.random() * 1e9 );
	Game.AddCommand( "+" + cmd, HoldStart, "", 0 );
	Game.AddCommand( "-" + cmd, HoldEnd, "", 0 );
	Game.CreateCustomKeyBind( "SPACE", "+" + cmd );
	// While the scene plays, mouse clicks must not reach the world (no orders, no camera drags)
	GameUI.SetMouseCallback( function( eventName, arg ) { return state.active; } );
	GameEvents.Subscribe( "mcp_lab_cut_start", OnStart );
	GameEvents.Subscribe( "mcp_lab_cut_shot", OnShot );
	GameEvents.Subscribe( "mcp_lab_cut_shake", OnShake );
	GameEvents.Subscribe( "mcp_lab_cut_camera", OnCamera );
	GameEvents.Subscribe( "mcp_lab_cut_end", OnEnd );
	GameEvents.Subscribe( "mcp_lab_cut_probe", OnProbe );
	GameEvents.Subscribe( "mcp_lab_cut_autohold", OnAutoHold );
	Tick();
} )();
