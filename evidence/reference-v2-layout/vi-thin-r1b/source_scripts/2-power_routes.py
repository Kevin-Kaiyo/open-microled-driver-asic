"""Add real supply-only copper/via straps to the unchanged base MOS layout.

Original devices and signal polygons remain intact. M5 trunks and M4 port
feeds bypass long thin rails; M2 source/body legs use three actual via1 cuts.
All added copper is extracted. Nothing is patched into a SPICE RC deck.
"""


def add(c, path, nets):
    assert nets and set(nets) <= set(c["ports"])
    text = path.read_text()
    new = []
    added_routes = []

    def rect(net, layer, x0,y0,x1,y1):
        coords=[round(v,6) for v in [x0,y0,x1,y1]]
        assert all(abs(v/.005-round(v/.005))<1e-6 for v in coords)
        new.append("rect "+layer+" "+" ".join(map(str,coords)))
        added_routes.append(dict(net=net,layer=layer,rect_um=coords,purpose="supply-only additional strap"))

    def via(net,low,high,cut,x,y):
        for layer in (low,high):
            rect(net,layer,x-.19,y-.19,x+.19,y+.19)
        half=.13 if cut=="via1" else .14
        rect(net,cut,x-half,y-half,x+half,y+half)

    trunks=[]
    for i,net in enumerate(nets):
        trunk_y=60+10*i
        assert trunk_y+3<98, "Keep new supply trunks below active device rows"
        x0,x1=c["bus_spans_um"][net]
        anchor_x,anchor_y=c["port_anchor_um"][net]
        feed_x=anchor_x-4
        # Continuous wide top-metal trunk. Original narrow M3 remains intact.
        rect(net,"metal5",min(x0-1,feed_x-1),trunk_y-3,x1+1,trunk_y+3)
        # Port feed is M4 so it crosses other M5 supply trunks without contact.
        rect(net,"metal4",anchor_x-.8,min(anchor_y,trunk_y)-.19,
             anchor_x+.8,max(anchor_y,trunk_y)+.19)
        rect(net,"metal4",feed_x-.8,trunk_y-.8,anchor_x+.8,trunk_y+.8)
        rect(net,"metal3",anchor_x-.79,anchor_y-.19,anchor_x+.79,anchor_y+.19)
        for dx in (-.6,0,.6):
            via(net,"metal3","metal4","via3",anchor_x+dx,anchor_y)
            via(net,"metal4","metal5","via4",feed_x+dx,trunk_y)
        terminals=[]
        for d in c["devices"]:
            for pin,n in zip("DGSB",d["nodes"]):
                if n!=net:
                    continue
                assert pin!="G", "Supply strap only supports current/body terminals"
                x,y=d["pins_um"][pin]
                assert d["w_um"]>=2, "Three-row contact array requires W >= 2um"
                # Supply source/body connection with three parallel actual cuts.
                rect(net,"metal2",x-.5,min(trunk_y,y)-.79,x+.5,max(trunk_y,y)+.79)
                if pin=="B":
                    ringx=d["cx"]-d["l_um"]/2-.98
                    rect(net,"metal1",x-.19,y-.79,ringx+.15,y+.79)
                else:
                    rect(net,"metal1",x-.19,y-.79,x+.19,y+.79)
                for layer in ("metal3","metal4"):
                    rect(net,layer,x-.19,trunk_y-.79,x+.19,trunk_y+.79)
                for dy in (-.6,0,.6):
                    via(net,"metal1","metal2","via1",x,y+dy)
                    via(net,"metal2","metal3","via2",x,trunk_y+dy)
                    via(net,"metal3","metal4","via3",x,trunk_y+dy)
                    via(net,"metal4","metal5","via4",x,trunk_y+dy)
                terminals.append(dict(instance=d["name"],pin=pin,coordinate_um=[x,y],via_rows=3))
        trunks.append(dict(net=net,layer="metal5",width_um=6,y_um=trunk_y,
            span_um=[min(x0-1,feed_x-1),x1+1],feed_layer="metal4",feed_width_um=1.6,
            source_body_leg_layer="metal2",source_body_leg_width_um=1,
            terminals=terminals))
    marker="select top cell\ndrc style drc(full)"
    assert marker in text
    path.write_text(text.replace(marker,"\n".join(new)+"\n"+marker))
    c["routes"] += added_routes
    c["power_routing"]=dict(kind="additional actual copper and via arrays",trunks=trunks,
        original_geometry_removed=False,devices_changed=False,
        original_thin_power_rails_retained=True,all_added_geometry_extracted=True)
