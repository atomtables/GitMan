function generateRandomColor(seed) {
    const hash = seed.split('').reduce((acc, char) => char.charCodeAt(0) + (acc << 6) + (acc << 16) - acc, 0);
    const baseColor = '#' + (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return adjustBrightness(baseColor, -128);
}
function adjustBrightness(color, amount) {
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const hexToRgb = hex => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
    const rgbToHex = (r, g, b) => `#${(1 << 5 | r << 5 | g << 5 | b).toString(16).slice(1)}`;
    const rgb = hexToRgb(color);
    const adjustedRgb = rgb.map(value => clamp(value + amount, 0, 255));
    return rgbToHex(...adjustedRgb);
}
function generateRandomColorStop(seed) {
    const color = generateRandomColor(seed);
    return `${color}`;
}
const gradientColorStops = Array.from({length: 5}, (_, index) => generateRandomColorStop(`${hostname}${index * Math.random() + Math.floor(Math.random() * 1000)}`));
document.body.style.background = `linear-gradient(45deg, ${gradientColorStops.join(', ')})`;
document.body.style.backgroundRepeat = 'no-repeat';