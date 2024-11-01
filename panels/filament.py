import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel
from ks_includes.functions import parse_bool
# -*- coding: UTF-8 -*- 

class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Filament")
        super().__init__(screen, title)
        self.devices = {}
        # Create a grid for all devices
        self.labels['devices'] = Gtk.Grid(valign=Gtk.Align.CENTER)

        self.load_pins()
        #modified_here
        self.buttons = {
            'filament': self._gtk.Button("filament", _("手动进料"), "color4")
        }
        self.buttons['filament'].connect("clicked", self.extrude)
        self.labels['devices'].attach(self.buttons['filament'], 0, 5, 1, 1)
        
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['devices'])

        self.content.add(scroll)
        
    #modified_here
    def extrude(self, widget):
          
          
        self._screen._send_action(widget, "printer.gcode.script",{"script": f"CHARGE"})
        logging.info(f"1321")
          
    def load_pins(self):
        output_pins = self._printer.get_pwm_tools() + self._printer.get_output_pins()
        
        self.add_pin(f"output_pin 启动供料系统并检测断料")
        
    def add_pin(self, pin):
        logging.info(f"Adding pin: {pin}")

        name = Gtk.Label(
            hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        name.set_markup(f'\n<big><b>{" ".join(pin.split(" ")[1:])}</b></big>\n')

        self.devices[pin] = {}
        section = self._printer.get_config_section(pin)
        if parse_bool(section.get('pwm', 'false')) or parse_bool(section.get('hardware_pwm', 'false')):
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            scale.set_value(self.check_pin_value(pin))
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            self.devices[pin]['scale'] = scale
            scale.connect("button-release-event", self.set_output_pin, pin)

            min_btn = self._gtk.Button("cancel", None, "color1", 1)
            min_btn.set_hexpand(False)
            min_btn.connect("clicked", self.update_pin_value, pin, 0)
            pin_col = Gtk.Box(spacing=5)
            pin_col.add(min_btn)
            pin_col.add(scale)
            self.devices[pin]["row"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.devices[pin]["row"].add(name)
            self.devices[pin]["row"].add(pin_col)
        else:
            self.devices[pin]['switch'] = Gtk.Switch()
            self.devices[pin]['switch'].connect("notify::active", self.set_output_pin, pin)
            self.devices[pin]["row"] = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            self.devices[pin]["row"].add(name)
            self.devices[pin]["row"].add(self.devices[pin]['switch'])

        pos = sorted(self.devices).index(pin)
        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(self.devices[pin]['row'], 0, pos, 1, 1)
        self.labels['devices'].show_all()

    def set_output_pin(self, widget, event, pin):
        if isinstance(widget, Gtk.Switch):
            widget.set_sensitive(False)
        if 'scale' in self.devices[pin]:
            value = self.devices[pin]["scale"].get_value() / 100
        elif 'switch' in self.devices[pin]:
            value = 0 if self.devices[pin]['switch'].get_active() else 1
        else:
            logging.error(f'unknown value for {widget} {event} {pin}')
            return
        self._screen._ws.klippy.gcode_script(f'SET_PIN PIN={" ".join(pin.split(" ")[1:])} VALUE={value}')
        GLib.timeout_add_seconds(1, self.check_pin_value, pin, widget)

    def check_pin_value(self, pin, widget=None):
        self.update_pin_value(None, pin, self._printer.get_pin_value(pin))
        if widget and isinstance(widget, Gtk.Switch):
            widget.set_sensitive(True)
        return False

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for pin in self.devices:
            if pin in data and "value" in data[pin]:
                self.update_pin_value(None, pin, data[pin]["value"])

    def update_pin_value(self, widget, pin, value):
        if pin not in self.devices:
            return
        if 'scale' in self.devices[pin]:
            self.devices[pin]['scale'].disconnect_by_func(self.set_output_pin)
            self.devices[pin]['scale'].set_value(round(float(value) * 100))
            self.devices[pin]['scale'].connect("button-release-event", self.set_output_pin, pin)
        elif 'switch' in self.devices[pin]:
            self.devices[pin]['switch'].set_active(value == 0)
        if widget is not None:
            self.set_output_pin(widget, None, pin)
