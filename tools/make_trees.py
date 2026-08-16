#!/usr/bin/env python3
"""宝樹の3パターンをBlender(bpy)で生成してglb出力する。

使い方: python3 tools/make_trees.py
出力: public/assets/tree_conifer.glb / tree_broadleaf.glb / tree_weeping.glb

前提: pip install bpy (Blender 5.x ヘッドレス)
"""
import math
import random
import sys

import bpy
import bmesh
from mathutils import Vector

OUT_DIR = "public/assets"


# ---------------------------------------------------------------- 共通

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name, color, metallic, roughness, emission=None, emission_strength=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


GOLD_TRUNK = (0.55, 0.38, 0.12)
GOLD_LEAF = (0.85, 0.62, 0.2)
PALE_LEAF = (0.92, 0.9, 0.85)  # 実行時に四宝の色を乗せられる明るい葉


def clouds_texture(name, scale):
    tex = bpy.data.textures.new(name, "CLOUDS")
    tex.noise_scale = scale
    return tex


def displace(obj, scale, strength):
    mod = obj.modifiers.new("displace", "DISPLACE")
    mod.texture = clouds_texture(obj.name + "_noise", scale)
    mod.strength = strength


def subsurf(obj, levels):
    mod = obj.modifiers.new("subsurf", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels


def shade_smooth(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def join(objects, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined


def triangle_count():
    total = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            mesh = obj.evaluated_get(depsgraph).to_mesh()
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
    return total


def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_apply=True)
    print(f"  -> {path} ({triangle_count()} tris)")


# 骨格(頂点と辺)からスキンモディファイアで幹・枝をつくる
def skeleton_tree(name, seed, height, levels, children, spread, radius0):
    random.seed(seed)
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    tips = []  # (Vector, depth)

    def grow(base_vert, direction, length, depth):
        tip = base_vert.co + direction * length
        tip_vert = bm.verts.new(tip)
        bm.edges.new((base_vert, tip_vert))
        if depth >= levels:
            tips.append((Vector(tip), depth))
            return
        count = children if depth > 0 else max(children, 3)
        for _ in range(count):
            axis = Vector((random.uniform(-1, 1), random.uniform(-1, 1), 0.3)).normalized()
            new_dir = (direction * (1 - spread) + axis * spread).normalized()
            grow(tip_vert, new_dir, length * random.uniform(0.55, 0.72), depth + 1)

    root = bm.verts.new((0, 0, 0))
    grow(root, Vector((random.uniform(-0.08, 0.08), random.uniform(-0.08, 0.08), 1)).normalized(), height * 0.45, 0)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    skin = obj.modifiers.new("skin", "SKIN")
    skin.use_smooth_shade = True
    # 根元から先端へ細くする
    verts = obj.data.skin_vertices[0].data
    coords = [v.co.z for v in obj.data.vertices]
    zmax = max(coords) or 1
    for v, mv in zip(verts, obj.data.vertices):
        t = mv.co.z / zmax
        r = radius0 * (1 - 0.82 * t)
        v.radius = (r, r)
    subsurf(obj, 1)
    return obj, tips


# ---------------------------------------------------------------- パターン1: 針葉宝樹

def build_conifer(path):
    reset_scene()
    trunk_mat = make_material("trunk", GOLD_TRUNK, 0.85, 0.45)
    leaf_mat = make_material("foliage", PALE_LEAF, 0.4, 0.5)

    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.26, radius2=0.04, depth=7.2, location=(0, 0, 3.6))
    trunk = bpy.context.active_object
    trunk.data.materials.append(trunk_mat)
    shade_smooth(trunk)

    tiers = []
    random.seed(7)
    for i in range(5):
        t = i / 4
        radius = 2.3 * (1 - 0.68 * t)
        depth = 1.9 - 0.7 * t
        z = 1.3 + t * 4.4
        bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=radius, radius2=0.03, depth=depth,
                                        location=(0, 0, z + depth / 2))
        tier = bpy.context.active_object
        subsurf(tier, 2)
        displace(tier, 0.45, 0.14)
        shade_smooth(tier)
        tiers.append(tier)
    foliage = join(tiers, "foliage")
    foliage.data.materials.append(leaf_mat)

    # 頂の宝珠
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.24, location=(0, 0, 7.3))
    hoju = bpy.context.active_object
    hoju.scale = (1, 1, 1.3)
    hoju.data.materials.append(make_material("hoju", (1.0, 0.9, 0.6), 0.9, 0.15, (1.0, 0.85, 0.5), 2.0))
    shade_smooth(hoju)

    export(path)


# ---------------------------------------------------------------- パターン2: 金葉樹(広葉)

def build_broadleaf(path):
    reset_scene()
    trunk_mat = make_material("trunk", GOLD_TRUNK, 0.85, 0.45)
    leaf_mat = make_material("foliage", (1.0, 0.76, 0.28), 0.9, 0.32)

    trunk, tips = skeleton_tree("trunk", seed=11, height=6.2, levels=3, children=3, spread=0.55, radius0=0.3)
    trunk.data.materials.append(trunk_mat)

    clumps = []
    random.seed(23)
    for tip, _depth in tips:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(0.5, 0.8),
                                              location=(tip.x, tip.y, tip.z + 0.1))
        clump = bpy.context.active_object
        clump.scale = (1.2, 1.2, 0.75)
        displace(clump, 0.4, 0.28)
        shade_smooth(clump)
        clumps.append(clump)
    foliage = join(clumps, "foliage")
    foliage.data.materials.append(leaf_mat)

    export(path)


# ---------------------------------------------------------------- パターン3: 垂宝樹(枝垂れ)

def build_weeping(path):
    reset_scene()
    trunk_mat = make_material("trunk", GOLD_TRUNK, 0.85, 0.45)
    strand_mat = make_material("strand", GOLD_LEAF, 0.9, 0.3)
    jewel_mat = make_material("jewel", (1.0, 0.95, 0.75), 0.6, 0.1, (1.0, 0.9, 0.6), 2.5)

    trunk, tips = skeleton_tree("trunk", seed=31, height=6.5, levels=2, children=3, spread=0.5, radius0=0.28)
    trunk.data.materials.append(trunk_mat)

    random.seed(41)
    strands = []
    jewels = []
    for tip, _depth in tips:
        for _ in range(5):
            # 弧を描いて垂れる房をポリラインでつくり、ベベルで太らせる
            curve = bpy.data.curves.new("strand", "CURVE")
            curve.dimensions = "3D"
            curve.bevel_depth = 0.022
            curve.bevel_resolution = 3
            spline = curve.splines.new("NURBS")
            length = random.uniform(2.2, 3.4)
            direction = Vector((random.uniform(-1, 1), random.uniform(-1, 1), 0)).normalized()
            points = []
            for step in range(8):
                s = step / 7
                out = direction * (0.35 * math.sin(s * math.pi * 0.5)) * length * 0.45
                down = Vector((0, 0, -1)) * (s * s) * length
                p = Vector(tip) + out + down
                points.append(p)
            spline.points.add(len(points) - 1)
            for pt, p in zip(spline.points, points):
                pt.co = (p.x, p.y, p.z, 1)
            spline.use_endpoint_u = True  # 端点を通す(宝玉が房の先端に密着するように)
            obj = bpy.data.objects.new("strand", curve)
            bpy.context.collection.objects.link(obj)
            strands.append(obj)
            # 房の先に宝玉
            end = points[-1]
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.075, location=(end.x, end.y, end.z))
            shade_smooth(bpy.context.active_object)
            jewels.append(bpy.context.active_object)

    # カーブをメッシュ化して結合
    bpy.ops.object.select_all(action="DESELECT")
    for s in strands:
        s.select_set(True)
    bpy.context.view_layer.objects.active = strands[0]
    bpy.ops.object.convert(target="MESH")
    strand_meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    strand_obj = join(strand_meshes, "strands")
    strand_obj.data.materials.append(strand_mat)
    shade_smooth(strand_obj)

    jewel_obj = join(jewels, "jewels")
    jewel_obj.data.materials.append(jewel_mat)

    export(path)


if __name__ == "__main__":
    build_conifer(f"{OUT_DIR}/tree_conifer.glb")
    build_broadleaf(f"{OUT_DIR}/tree_broadleaf.glb")
    build_weeping(f"{OUT_DIR}/tree_weeping.glb")
    print("done", file=sys.stderr)
